"""
报告生成器模块
负责生成各种格式的分析报告
"""

import asyncio
import base64
import html
import os
import re
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from urllib.parse import quote

import aiohttp
import ulid
from diskcache import Cache
from markupsafe import Markup

from ...domain.repositories.report_repository import IReportGenerator
from ...utils.logger import logger
from ..utils.template_utils import render_template
from ..visualization.activity_charts import ActivityVisualizer
from .templates import HTMLTemplates

MAX_CONCURRENT_DOWNLOADS = 10
AVATAR_CACHE_EXPIRE_TIME = 259200


class ReportGenerator(IReportGenerator):
    """报告生成器"""

    def __init__(self, config_manager, data_dir):
        self._avatar_session = None
        self.config_manager = config_manager
        self.data_dir = data_dir
        self.activity_visualizer = ActivityVisualizer()
        self.html_templates = HTMLTemplates(config_manager)  # 实例化HTML模板管理器
        # 全局 T2I 渲染信号量，保护本地资源
        # 使用专用的 T2I 并发配置项
        max_concurrent = self.config_manager.get_t2i_max_concurrent()
        self._render_semaphore = asyncio.Semaphore(max_concurrent)

        # 运行时缓存，用于在一次分析任务中避免重复下载同一个头像
        self._avatar_cache = Cache(
            str(self.data_dir / "avatar")
        )  # user_id -> base64_uri
        self._avatar_session_concurrent_semaphore = asyncio.Semaphore(
            MAX_CONCURRENT_DOWNLOADS
        )
        self._avatar_session = None

    @staticmethod
    def _sanitize_path_component(name: str) -> str:
        """消毒单个路径/文件名片段，禁止路径穿越和非法字符。"""
        # 禁止空组件、相对路径控制符："."、".."
        if not name or name in {".", ".."}:
            raise ValueError(f"无效的路径片段: {name!r}")

        # 不允许包含路径分隔符
        name = name.replace("/", "_")
        name = name.replace("\\", "_")

        # 去除非打印字符和非法文件名字符
        name = re.sub(r'[\x00-\x1f<>:"|?*]', "_", name)

        # 保留中文、字母、数字、下划线、横线和点
        name = name.strip()
        if not name:
            raise ValueError("路径片段经过消毒后为空")

        return name

    def _build_safe_report_path(
        self,
        output_dir: Path,
        filename_format: str,
        group_id: str,
        date: str,
    ) -> Path:
        """根据格式构建安全输出路径，支持子目录和 {ulid}。"""
        generated_ulid = str(ulid.new())
        safe_context = {
            "group_id": group_id,
            "date": date,
            "ulid": generated_ulid,
        }

        try:
            formatted = render_template(filename_format, strict=True, **safe_context)
        except Exception as e:
            raise ValueError(f"文件名模板渲染失败: {e}") from e

        if os.path.isabs(formatted):
            raise ValueError("文件名格式不得为绝对路径")

        relative_path = Path(formatted)
        sanitized_parts = []
        for part in relative_path.parts:
            if part in {".", ".."}:
                raise ValueError("路径中不得包含 '.' 或 '..'。")
            sanitized_parts.append(self._sanitize_path_component(part))

        safe_relative = Path(*sanitized_parts)

        output_dir_resolved = output_dir.resolve(strict=False)
        target_path = (output_dir_resolved / safe_relative).resolve(strict=False)

        # 防止回退到上级目录（使用 Path.relative_to 进行目录包含校验）
        try:
            target_path.relative_to(output_dir_resolved)
        except ValueError:
            raise ValueError("文件路径不在输出目录之内，可能包含路径穿越")

        # 防止与已有文件覆盖（如果用户格式没有唯一标记），追加 ULID 后缀
        if target_path.exists():
            suffix = target_path.suffix
            stem = target_path.stem
            target_path = target_path.with_name(f"{stem}_{generated_ulid}{suffix}")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        return target_path

    async def generate_image_report(
        self,
        analysis_result: dict,
        group_id: str,
        html_render_func,
        avatar_url_getter=None,
        nickname_getter=None,
    ) -> tuple[str | None, str | None]:
        """
        生成图片格式的分析报告

        Args:
            analysis_result: 分析结果字典
            group_id: 群组ID
            html_render_func: HTML渲染函数
            avatar_url_getter: 异步回调函数，接收 user_id 返回 avatar_url/data
            nickname_getter: 昵称获取函数

        Returns:
            tuple[str | None, str | None]: (image_url, html_content)
        """
        html_content = None
        try:
            # 准备渲染数据
            render_payload = await self._prepare_render_data(
                analysis_result,
                chart_template="activity_chart.html",
                avatar_url_getter=avatar_url_getter,
                nickname_getter=nickname_getter,
            )

            # 先渲染HTML模板（使用 Jinja2 渲染器以支持逻辑标签）
            html_content = self.html_templates.render_template(
                "image_template.html", **render_payload
            )

            # 检查HTML内容是否有效
            if not html_content:
                logger.error("图片报告HTML渲染失败：返回空内容")
                return None, None

            logger.info(f"图片报告HTML渲染完成，长度: {len(html_content)} 字符")

            # 使用信号量控制并发进入渲染引擎
            async with self._render_semaphore:
                logger.debug(f"[T2I] 已进入渲染队列 (群: {group_id})")

                # 定义渲染策略
                render_strategies = [
                    # 1. 第一策略: PNG, Ultra quality, Device scale
                    {
                        "full_page": True,
                        "type": "png",
                        "scale": "device",
                        "device_scale_factor_level": "ultra",
                    },
                    # 2. 第二策略: JPEG, ultra, quality 100%, Device scale
                    {
                        "full_page": True,
                        "type": "jpeg",
                        "quality": 100,
                        "scale": "device",
                        "device_scale_factor_level": "ultra",
                    },
                    # 3. 第三策略: JPEG, high, quality 80%, Device scale
                    {
                        "full_page": True,
                        "type": "jpeg",
                        "quality": 95,
                        "scale": "device",
                        "device_scale_factor_level": "high",  # 尝试高分辨率
                    },
                    # 4. 第四策略: JPEG, normal quality, Device scale (后备)
                    {
                        "full_page": True,
                        "type": "jpeg",
                        "quality": 80,
                        "scale": "device",
                        # normal quality
                    },
                ]

                last_exception = None

                for image_options in render_strategies:
                    try:
                        # Cleanse options
                        if image_options.get("type") == "png":
                            image_options["quality"] = None

                        logger.info(f"正在尝试渲染策略: {image_options}")
                        # 改为获取 bytes 数据，避免 OneBot 无法访问内部 URL
                        image_data = await html_render_func(
                            html_content,  # 渲染后的HTML内容
                            {},  # 空数据字典，因为数据已包含在HTML中
                            False,  # return_url=False，直接获取图片数据
                            image_options,
                        )

                        if image_data:
                            # 校验是否为合法图片（防止 T2I 返回 500 错误 HTML 字符流）
                            is_valid = False
                            actual_data_head = None

                            if isinstance(image_data, bytes):
                                actual_data_head = image_data[:10]
                            elif isinstance(image_data, str) and os.path.exists(
                                image_data
                            ):
                                try:
                                    with open(image_data, "rb") as f:
                                        actual_data_head = f.read(10)
                                except Exception as e:
                                    logger.warning(f"读取图片临时文件失败: {e}")

                            if actual_data_head:
                                # 检查 magic numbers (JPEG: FF D8, PNG: 89 50 4E 47)
                                if actual_data_head.startswith(
                                    b"\xff\xd8"
                                ) or actual_data_head.startswith(b"\x89PNG"):
                                    is_valid = True
                                else:
                                    logger.warning(
                                        f"渲染结果似乎不是有效的图片数据 (头部: {actual_data_head.hex()})"
                                    )

                            if is_valid:
                                if isinstance(image_data, bytes):
                                    b64 = base64.b64encode(image_data).decode("utf-8")
                                    image_url = f"base64://{b64}"
                                    logger.info(
                                        f"图片生成成功 ({image_options}): [Base64 Data {len(image_data)} bytes]"
                                    )
                                    return image_url, html_content
                                elif isinstance(image_data, str):
                                    logger.info(f"图片生成成功 (String): {image_data}")
                                    return image_data, html_content

                        logger.warning(f"渲染策略 {image_options} 返回了无效或空数据")

                    except Exception as e:
                        logger.warning(f"渲染策略 {image_options} 失败: {e}")
                        last_exception = e
                        logger.warning("尝试下一个策略")
                        continue

                # 如果所有策略都失败
                logger.error(f"所有渲染策略都失败。最后一个错误: {last_exception}")
                return None, html_content

        except Exception as e:
            logger.error(f"生成图片报告过程发生严重错误: {e}", exc_info=True)
            return None, html_content
        finally:
            # 清理本次运行的 session 和缓存
            if self._avatar_session:
                await self._avatar_session.close()
                self._avatar_session = None

    async def generate_pdf_report(
        self,
        analysis_result: dict,
        group_id: str,
        avatar_getter=None,
        nickname_getter=None,
    ) -> str | None:
        """生成PDF格式的分析报告"""
        try:
            # 确保输出目录存在（使用 asyncio.to_thread 避免阻塞）
            output_dir = Path(self.config_manager.get_pdf_output_dir())
            await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)

            # 生成文件路径，支持 {group_id}/{date}/{ulid} 自定义子目录
            current_date = datetime.now().strftime("%Y%m%d")
            pdf_path = self._build_safe_report_path(
                output_dir,
                self.config_manager.get_pdf_filename_format(),
                group_id=group_id,
                date=current_date,
            )

            # 准备渲染数据
            render_data = await self._prepare_render_data(
                analysis_result,
                chart_template="activity_chart_pdf.html",
                avatar_url_getter=avatar_getter,
                nickname_getter=nickname_getter,
            )
            logger.info(f"PDF 渲染数据准备完成，包含 {len(render_data)} 个字段")

            # 生成 HTML 内容（使用 Jinja2 渲染器以支持逻辑标签）
            html_content = self.html_templates.render_template(
                "pdf_template.html", **render_data
            )

            # 检查HTML内容是否有效
            if not html_content:
                logger.error("PDF报告HTML渲染失败：返回空内容")
                return None

            logger.info(f"HTML 内容生成完成，长度: {len(html_content)} 字符")

            # 转换为 PDF
            success = await self._html_to_pdf(html_content, str(pdf_path))

            if success:
                return str(pdf_path.absolute())
            else:
                return None

        except Exception as e:
            logger.error(f"生成 PDF 报告失败: {e}")
            return None

    async def generate_html_report(
        self,
        analysis_result: dict,
        group_id: str,
        avatar_url_getter=None,
        nickname_getter=None,
    ) -> tuple[str | None, str | None]:
        """
        生成HTML格式的分析报告，保存到指定目录

        Args:
            analysis_result: 分析结果字典
            group_id: 群组ID
            avatar_url_getter: 异步回调函数，接收 user_id 返回 avatar_url/data
            nickname_getter: 昵称获取函数

        Returns:
            tuple[str | None, str | None]: (html_path, json_path) - HTML文件路径和JSON文件路径
        """
        try:
            import json

            # 确保输出目录存在（使用 asyncio.to_thread 避免阻塞）
            output_dir = Path(self.config_manager.get_html_output_dir())
            await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)

            # 生成文件路径
            current_date = datetime.now().strftime("%Y%m%d")
            base_html_path = self._build_safe_report_path(
                output_dir,
                self.config_manager.get_html_filename_format(),
                group_id=group_id,
                date=current_date,
            )

            html_path = base_html_path
            if not html_path.suffix:
                html_path = html_path.with_suffix(".html")

            json_path = html_path.with_suffix(".json")

            html_path.parent.mkdir(parents=True, exist_ok=True)

            # 准备渲染数据
            render_data = await self._prepare_render_data(
                analysis_result,
                chart_template="activity_chart.html",
                avatar_url_getter=avatar_url_getter,
                nickname_getter=nickname_getter,
            )
            logger.info(f"HTML 渲染数据准备完成，包含 {len(render_data)} 个字段")

            # 生成 HTML 内容（使用 Jinja2 渲染器，尝试 html_template.html，失败则回退到 image_template.html）
            html_content = None
            try:
                html_content = self.html_templates.render_template(
                    "html_template.html", **render_data
                )
                logger.info("使用 html_template.html 渲染成功")
            except Exception as e:
                logger.warning(
                    f"html_template.html 不存在或渲染失败，回退到 image_template.html: {e}"
                )
                html_content = self.html_templates.render_template(
                    "image_template.html", **render_data
                )
                logger.info("使用 image_template.html 渲染成功")

            # 检查HTML内容是否有效
            if not html_content:
                logger.error("HTML报告渲染失败：返回空内容")
                return None, None

            logger.info(f"HTML 内容生成完成，长度: {len(html_content)} 字符")

            # 保存 HTML 文件
            await asyncio.to_thread(
                html_path.write_text, html_content, encoding="utf-8"
            )
            logger.info(f"HTML 报告已保存: {html_path}")

            def json_default_encoder(obj):
                if hasattr(obj, "to_dict") and callable(obj.to_dict):
                    return obj.to_dict()
                if is_dataclass(obj) and not isinstance(obj, type):
                    return asdict(obj)
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                if isinstance(obj, Enum):
                    return obj.value
                if isinstance(obj, (set, tuple)):
                    return list(obj)
                raise TypeError(
                    f"Object of type {type(obj).__name__} is not JSON serializable"
                )

            # 保存原始 JSON 数据
            json_data = {
                "analysis_result": analysis_result,
                "group_id": group_id,
                "generated_at": datetime.now().isoformat(),
            }
            await asyncio.to_thread(
                json_path.write_text,
                json.dumps(
                    json_data,
                    ensure_ascii=False,
                    indent=2,
                    default=json_default_encoder,
                ),
                encoding="utf-8",
            )
            logger.info(f"JSON 数据已保存: {json_path}")

            return str(html_path.absolute()), str(json_path.absolute())

        except Exception as e:
            logger.error(f"生成 HTML 报告失败: {e}", exc_info=True)
            return None, None

    def build_html_caption(self, html_path: str) -> str:
        """根据 html_base_url 生成 HTML 报告链接 caption"""

        caption = "📊 每日群聊分析报告已生成"
        base_url = self.config_manager.get_html_base_url()
        if not base_url or not html_path:
            return caption

        # 支持 html_filename_format 中的子目录，保持相对路径
        output_dir = Path(self.config_manager.get_html_output_dir()).resolve(
            strict=False
        )
        try:
            relative_path = (
                Path(html_path).resolve(strict=False).relative_to(output_dir)
            )
            relative_url = str(relative_path).replace(os.sep, "/")
        except Exception:
            relative_url = Path(html_path).name

        encoded_relative_url = quote(relative_url, safe="/")
        return caption + f"\n{base_url.rstrip('/')}/{encoded_relative_url}"

    def generate_text_report(self, analysis_result: dict) -> str:
        """生成文本格式的分析报告"""
        stats = analysis_result["statistics"]
        topics = analysis_result["topics"]
        user_titles = analysis_result["user_titles"]

        report = f"""
🎯 群聊日常分析报告
📅 {datetime.now().strftime("%Y年%m月%d日")}

📊 基础统计
• 消息总数: {stats.message_count}
• 参与人数: {stats.participant_count}
• 总字符数: {stats.total_characters}
• 表情数量: {stats.emoji_count}
• 最活跃时段: {stats.most_active_period}

💬 热门话题
"""

        max_topics = self.config_manager.get_max_topics()
        for i, topic in enumerate(topics[:max_topics], 1):
            contributors_str = "、".join(topic.contributors)
            report += f"{i}. {topic.topic}\n"
            report += f"   参与者: {contributors_str}\n"
            report += f"   {topic.detail}\n\n"

        report += "🏆 群友称号\n"
        max_user_titles = self.config_manager.get_max_user_titles()
        for title in user_titles[:max_user_titles]:
            report += f"• {title.name} - {title.title} ({title.mbti})\n"
            report += f"  {title.reason}\n\n"

        report += "💬 群圣经\n"
        max_golden_quotes = self.config_manager.get_max_golden_quotes()
        for i, golden_quote in enumerate(stats.golden_quotes[:max_golden_quotes], 1):
            report += f'{i}. "{golden_quote.content}" —— {golden_quote.sender}\n'
            report += f"   {golden_quote.reason}\n\n"

        return report

    async def _prepare_render_data(
        self,
        analysis_result: dict,
        chart_template: str = "activity_chart.html",
        avatar_url_getter=None,
        nickname_getter=None,
    ) -> dict:
        """准备渲染数据"""
        stats = analysis_result["statistics"]
        topics = analysis_result["topics"]
        user_titles = analysis_result["user_titles"]
        activity_viz = stats.activity_visualization

        # 使用Jinja2模板构建话题HTML（批量渲染）
        max_topics = self.config_manager.get_max_topics()
        topics_list = []
        user_analysis = analysis_result.get("user_analysis")

        for i, topic in enumerate(topics[:max_topics], 1):
            # 处理话题详情中的用户引用头像
            processed_detail = await self._render_mentions(
                topic.detail, avatar_url_getter, nickname_getter, user_analysis
            )
            topics_list.append(
                {
                    "index": i,
                    "topic": topic,
                    "contributors": "、".join(topic.contributors),
                    "detail": processed_detail,
                }
            )

        topics_html = self.html_templates.render_template(
            "topic_item.html", topics=topics_list
        )
        logger.info(f"话题HTML生成完成，长度: {len(topics_html)}")

        # 使用Jinja2模板构建用户称号HTML（批量渲染，包含头像）
        max_user_titles = self.config_manager.get_max_user_titles()
        titles_list = []
        for title in user_titles[:max_user_titles]:
            # 获取用户头像
            avatar_data = await self._get_user_avatar(
                str(title.user_id), avatar_url_getter
            )
            title_data = {
                "name": title.name,
                "title": title.title,
                "mbti": title.mbti,
                "reason": title.reason,
                "avatar_data": avatar_data,
            }
            titles_list.append(title_data)

        titles_html = self.html_templates.render_template(
            "user_title_item.html", titles=titles_list
        )
        logger.info(f"用户称号HTML生成完成，长度: {len(titles_html)}")

        # 使用Jinja2模板构建金句HTML（批量渲染）
        max_golden_quotes = self.config_manager.get_max_golden_quotes()
        quotes_list = []
        for golden_quote in stats.golden_quotes[:max_golden_quotes]:
            avatar_url = (
                await self._get_user_avatar(
                    str(golden_quote.user_id), avatar_url_getter
                )
                if golden_quote.user_id
                else None
            )
            # 处理解析锐评中的用户引用头像
            processed_reason = await self._render_mentions(
                golden_quote.reason, avatar_url_getter, nickname_getter, user_analysis
            )
            quotes_list.append(
                {
                    "content": golden_quote.content,
                    "sender": golden_quote.sender,
                    "reason": processed_reason,
                    "avatar_url": avatar_url,
                }
            )

        quotes_html = self.html_templates.render_template(
            "quote_item.html", quotes=quotes_list
        )
        logger.info(f"金句HTML生成完成，长度: {len(quotes_html)}")

        # 生成活跃度可视化HTML
        chart_data = self.activity_visualizer.get_hourly_chart_data(
            activity_viz.hourly_activity
        )
        hourly_chart_html = self.html_templates.render_template(
            chart_template, chart_data=chart_data
        )
        logger.info(f"活跃度图表HTML生成完成，长度: {len(hourly_chart_html)}")

        # 生成聊天质量锐评HTML
        chat_quality_html = ""
        chat_quality_review = analysis_result.get("chat_quality_review")
        if not chat_quality_review and hasattr(stats, "chat_quality_review"):
            chat_quality_review = stats.chat_quality_review

        if chat_quality_review:
            # 如果是对象，转为字典（为了统一渲染）
            if hasattr(chat_quality_review, "dimensions"):
                review_data = {
                    "title": chat_quality_review.title,
                    "subtitle": chat_quality_review.subtitle,
                    "dimensions": [
                        {
                            "name": d.name,
                            "percentage": d.percentage,
                            "comment": d.comment,
                            "color": d.color,
                        }
                        for d in chat_quality_review.dimensions
                    ],
                    "summary": chat_quality_review.summary,
                }
            else:
                review_data = chat_quality_review

            chat_quality_html = self.html_templates.render_template(
                "chat_quality_item.html", **review_data
            )
            logger.info(f"聊天质量锐评HTML生成完成，长度: {len(chat_quality_html)}")

        # 准备最终渲染数据
        render_data = {
            "current_date": datetime.now().strftime("%Y年%m月%d日"),
            "current_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message_count": stats.message_count,
            "participant_count": stats.participant_count,
            "total_characters": stats.total_characters,
            "emoji_count": stats.emoji_count,
            "most_active_period": stats.most_active_period,
            "topics_html": topics_html,
            "titles_html": titles_html,
            "quotes_html": quotes_html,
            "hourly_chart_html": hourly_chart_html,
            "chat_quality_html": chat_quality_html,
            "total_tokens": stats.token_usage.total_tokens
            if stats.token_usage.total_tokens
            else 0,
            "prompt_tokens": stats.token_usage.prompt_tokens
            if stats.token_usage.prompt_tokens
            else 0,
            "completion_tokens": stats.token_usage.completion_tokens
            if stats.token_usage.completion_tokens
            else 0,
        }

        logger.info(f"渲染数据准备完成，包含 {len(render_data)} 个字段")
        return render_data

    async def _render_mentions(
        self,
        text: str,
        avatar_url_getter,
        nickname_getter=None,
        user_analysis: dict | None = None,
    ) -> Markup:
        """
        处理文本，将 [123456] 格式的用户引用替换为头像+名称的胶囊样式
        """
        pattern = r"\[(\d+)\]"
        if not text:
            return Markup("")

        matches = list(re.finditer(pattern, text))
        if not matches:
            return self._escape_text_segment(text)

        async def render_capsule(match: re.Match[str]) -> Markup:
            uid = match.group(1)
            url = await self._get_user_avatar(
                uid, avatar_url_getter
            )  # 内部已有缓存，无需顶层并发获取

            name = None
            # 1. 尝试从 LLM 分析结果获取
            if user_analysis and uid in user_analysis:
                stats = user_analysis[uid]
                name = stats.get("nickname") or stats.get("name")
                if self._is_placeholder_display_name(name, uid):
                    name = None

            # 2. 尝试通过回调获取实时昵称
            if not name and nickname_getter:
                try:
                    name = await nickname_getter(uid)
                    if self._is_placeholder_display_name(name, uid):
                        name = None
                except Exception as e:
                    logger.warning(f"获取昵称失败 {uid}: {e}")

            # 胶囊样式 (Capsule Style) - 统一使用
            capsule_style = (
                "display:inline-flex;align-items:center;background:rgba(0,0,0,0.05);"
                "padding:2px 6px 2px 2px;border-radius:12px;margin:0 2px;"
                "vertical-align:middle;border:1px solid rgba(0,0,0,0.1);text-decoration:none;"
            )
            img_style = "width:18px;height:18px;border-radius:50%;margin-right:4px;display:block;"
            name_style = "font-size:0.85em;color:inherit;font-weight:500;line-height:1;"

            # 3. 最终后备: 确保有头像和名称
            final_url = url if url else self._get_default_avatar_base64()
            final_name = (
                name
                if (name and not self._is_placeholder_display_name(name, uid))
                else str(uid)
            )

            return Markup(
                f'<span class="user-capsule" style="{capsule_style}">'
                f'<img src="{html.escape(final_url, quote=True)}" style="{img_style}">'
                f'<span style="{name_style}">{html.escape(final_name)}</span>'
                "</span>"
            )

        result: list[Markup | str] = []
        last_end = 0
        for match in matches:
            result.append(self._escape_text_segment(text[last_end : match.start()]))
            result.append(await render_capsule(match))
            last_end = match.end()

        result.append(self._escape_text_segment(text[last_end:]))
        return Markup("").join(result)

    @staticmethod
    def _escape_text_segment(text: str) -> Markup:
        return Markup(html.escape(text, quote=False).replace("\n", "<br>"))

    @staticmethod
    def _is_placeholder_display_name(name: str | None, user_id: str) -> bool:
        """判断展示名称是否为占位值。"""
        if not name:
            return True
        normalized = str(name).strip()
        if not normalized:
            return True
        if normalized.lower() in {"unknown", "none", "null", "nil", "undefined"}:
            return True
        return normalized == str(user_id).strip()

    @staticmethod
    def _safe_url_for_log(url: str | None) -> str:
        """对日志中的 URL 进行脱敏，避免泄露 token。"""
        if not url:
            return ""
        # Telegram file URL: .../file/bot<token>/<file_path>
        return re.sub(r"/bot[^/]+/", "/bot<redacted>/", url)

    async def _get_user_avatar(self, avatar_id: str, avatar_url_getter=None) -> str:
        """
        获取用户头像的 Base64 Data URI。
        使用磁盘缓存，支持跨任务复用。获取失败时不缓存结果，以便后续请求重试。
        """
        # 1. 检查缓存 (仅包含成功的头像数据)
        if avatar_id in self._avatar_cache:
            data = self._avatar_cache[avatar_id]
            if isinstance(data, str):
                return data
            return str(data)

        # 2. 尝试获取头像字节流
        avatar_bytes = await self._get_user_avatar_bytes(avatar_id, avatar_url_getter)

        if not avatar_bytes:
            # 获取失败时返回默认头像，但不存入缓存，以便下次重试
            logger.warning(f"获取用户头像失败 {avatar_id}，本次将使用回退头像")
            return self._get_default_avatar_base64()

        # 3. 获取成功：转换并缓存
        avatar = self._b64_with_mime(avatar_bytes)
        if avatar:
            self._avatar_cache.set(avatar_id, avatar, expire=AVATAR_CACHE_EXPIRE_TIME)
            return avatar

        # 最终兜底
        return self._get_default_avatar_base64()

    def _b64_with_mime(self, _bytes: bytes) -> str | None:
        """将字节数据转换为 Base64 Data URI，并自动识别 MIME 类型。"""
        try:
            b64 = base64.b64encode(_bytes).decode("utf-8")
            # 简单判断 mime type
            mime = "image/jpeg"
            if _bytes.startswith(b"\x89PNG"):
                mime = "image/png"
            elif _bytes.startswith(b"GIF8"):
                mime = "image/gif"
            elif _bytes.startswith(b"RIFF") and b"WEBP" in _bytes[8:16]:
                mime = "image/webp"
            elif _bytes.startswith(b"\xff\xd8"):
                mime = "image/jpeg"

            return f"data:{mime};base64,{b64}"
        except Exception as e:
            logger.error(f"base64 转换失败: {e}", exc_info=True)
        return None

    async def _get_user_avatar_bytes(
        self, user_id: str, avatar_url_getter=None
    ) -> bytes | None:
        """核心头像获取逻辑"""
        file_content = None
        if not self._avatar_session:
            self._avatar_session = aiohttp.ClientSession(
                trust_env=True, timeout=aiohttp.ClientTimeout(total=15)
            )
        async with self._avatar_session_concurrent_semaphore:
            avatar_url = None
            if avatar_url_getter:
                try:
                    # avatar_url_getter 应该返回 URL
                    result = await avatar_url_getter(user_id)
                    if result:
                        if result.startswith("http"):
                            avatar_url = result
                        elif result.startswith("base64://"):
                            return base64.b64decode(result[len("base64://") :])
                        elif result.startswith("data:"):
                            parts = result.split(",", 1)
                            if len(parts) == 2:
                                return base64.b64decode(parts[1])
                        else:
                            logger.warning(
                                f"custom avatar_url_getter 返回了非 HTTP URL: {result[:50]}..."
                            )
                except Exception as e:
                    logger.warning(f"使用 custom avatar_url_getter 获取头像失败: {e}")

            if not avatar_url:
                if user_id.isdigit() and 5 <= len(user_id) <= 12:
                    # 强制使用 spec=40
                    avatar_url = (
                        f"https://q4.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=40"
                    )
                else:
                    # 其他平台若无 URL，无法获取头像
                    return None

            # 5. 下载并保存
            safe_avatar_url = self._safe_url_for_log(avatar_url)
            try:
                async with self._avatar_session.get(avatar_url) as response:
                    if response.status == 200:
                        content = await response.read()
                        if content:
                            # 校验文件头
                            is_valid_image = False
                            if content.startswith(b"\xff\xd8"):  # JPEG
                                is_valid_image = True
                            elif content.startswith(b"\x89PNG\r\n\x1a\n"):  # PNG
                                is_valid_image = True
                            elif content.startswith(b"GIF8"):  # GIF
                                is_valid_image = True
                            elif (
                                content.startswith(b"RIFF") and b"WEBP" in content[:16]
                            ):  # WebP
                                is_valid_image = True

                            if is_valid_image:
                                file_content = content
                            else:
                                logger.warning(
                                    f"下载的头像数据格式无效 ({safe_avatar_url})"
                                )
                    else:
                        logger.warning(
                            f"下载头像失败 {safe_avatar_url}: {response.status}"
                        )
            except Exception as e:
                logger.warning(f"下载头像网络错误 {safe_avatar_url}: {e}")

            return file_content

    def _get_default_avatar_base64(self) -> str:
        """返回默认头像 (灰色圆形占位符)"""
        # 一个简单的灰色圆圈 SVG 转 Base64
        svg = '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="50" fill="#ddd"/></svg>'
        b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64}"

    async def close(self):
        """释放资源，关闭缓存和 session"""
        if self._avatar_session:
            await self._avatar_session.close()
            self._avatar_session = None

        try:
            if self._avatar_cache:
                self._avatar_cache.close()
                logger.debug("头像缓存已关闭")
        except Exception as e:
            logger.warning(f"关闭头像缓存失败: {e}")

    async def _html_to_pdf(self, html_content: str, output_path: str) -> bool:
        """将 HTML 内容转换为 PDF 文件"""
        try:
            # 动态导入 playwright
            try:
                from playwright.async_api import async_playwright  # type: ignore
            except ImportError:
                logger.error("playwright 未安装，无法生成 PDF")
                logger.info("💡 请尝试运行: pip install playwright")
                return False

            import os
            import sys

            logger.info("启动浏览器进行 PDF 转换 (使用 Playwright)")

            async with async_playwright() as p:
                browser = None

                executable_path = None

                # 0. 优先检查配置的自定义路径
                custom_browser_path = self.config_manager.get_browser_path()
                if custom_browser_path:
                    if Path(custom_browser_path).exists():
                        logger.info(
                            f"使用配置的自定义浏览器路径: {custom_browser_path}"
                        )
                        executable_path = custom_browser_path
                    else:
                        logger.warning(
                            f"配置的浏览器路径不存在: {custom_browser_path}，尝试自动检测..."
                        )

                # 1. 如果没有自定义路径，尝试自动检测系统浏览器
                if not executable_path:
                    system_browser_paths = []
                    if sys.platform.startswith("win"):
                        username = os.environ.get("USERNAME", "")
                        local_app_data = os.environ.get(
                            "LOCALAPPDATA", rf"C:\Users\{username}\AppData\Local"
                        )
                        program_files = os.environ.get(
                            "ProgramFiles", r"C:\Program Files"
                        )
                        program_files_x86 = os.environ.get(
                            "ProgramFiles(x86)", r"C:\Program Files (x86)"
                        )

                        system_browser_paths = [
                            os.path.join(
                                program_files, r"Google\Chrome\Application\chrome.exe"
                            ),
                            os.path.join(
                                program_files_x86,
                                r"Google\Chrome\Application\chrome.exe",
                            ),
                            os.path.join(
                                local_app_data, r"Google\Chrome\Application\chrome.exe"
                            ),
                            os.path.join(
                                program_files_x86,
                                r"Microsoft\Edge\Application\msedge.exe",
                            ),
                            os.path.join(
                                program_files, r"Microsoft\Edge\Application\msedge.exe"
                            ),
                        ]
                    elif sys.platform.startswith("linux"):
                        system_browser_paths = [
                            "/usr/bin/google-chrome",
                            "/usr/bin/google-chrome-stable",
                            "/usr/bin/chromium",
                            "/usr/bin/chromium-browser",
                            "/snap/bin/chromium",
                        ]
                    elif sys.platform.startswith("darwin"):
                        system_browser_paths = [
                            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                            "/Applications/Chromium.app/Contents/MacOS/Chromium",
                        ]

                    # 尝试找到可用的系统浏览器
                    for path in system_browser_paths:
                        if Path(path).exists():
                            executable_path = path
                            logger.info(f"使用系统浏览器: {path}")
                            break

                # 定义默认启动参数
                launch_kwargs = {
                    "headless": True,
                    "args": [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--font-render-hinting=none",
                    ],
                }

                if executable_path:
                    launch_kwargs["executable_path"] = executable_path
                    launch_kwargs["channel"] = (
                        "chrome" if "chrome" in executable_path.lower() else "msedge"
                    )

                try:
                    if executable_path:
                        # 如果指定了路径，通常使用 chromium 启动
                        browser = await p.chromium.launch(**launch_kwargs)
                    else:
                        # 尝试直接启动，依赖 playwright install
                        logger.info("尝试启动 Playwright 托管的浏览器...")
                        browser = await p.chromium.launch(
                            headless=True, args=launch_kwargs["args"]
                        )

                except Exception as e:
                    logger.warning(f"浏览器启动失败: {e}")
                    if "Executable doesn't exist" in str(e) or "executable at" in str(
                        e
                    ):
                        logger.error("未找到可用的浏览器。")
                        logger.info(
                            "💡 请确保已安装 Playwright 浏览器: playwright install chromium"
                        )
                        logger.info("💡 或者安装 Google Chrome / Microsoft Edge")
                    return False

                if not browser:
                    return False

                try:
                    context = await browser.new_context(device_scale_factor=1)
                    page = await context.new_page()

                    # 设置页面内容
                    await page.set_content(
                        html_content, wait_until="networkidle", timeout=60000
                    )

                    # 生成 PDF
                    logger.info("开始生成 PDF...")
                    await page.pdf(
                        path=output_path,
                        format="A4",
                        print_background=True,
                        margin={
                            "top": "10mm",
                            "right": "10mm",
                            "bottom": "10mm",
                            "left": "10mm",
                        },
                    )
                    logger.info(f"PDF 生成成功: {output_path}")
                    return True

                except Exception as e:
                    logger.error(f"PDF 生成过程出错: {e}")
                    return False
                finally:
                    if browser:
                        await browser.close()

        except Exception as e:
            logger.error(f"Playwright 运行出错: {e}")
            return False
