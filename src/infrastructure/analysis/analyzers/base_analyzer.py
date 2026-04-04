"""
基础分析器抽象类
定义通用分析流程和接口
"""

from abc import ABC, abstractmethod
from collections.abc import Sized
from typing import Generic, TypeVar

from ....domain.models.data_models import TokenUsage
from ....utils.logger import logger
from ..utils.json_utils import parse_json_response
from ..utils.llm_utils import (
    call_provider_with_retry,
    extract_response_text,
    extract_token_usage,
    get_provider_id_with_fallback,
)
from ..utils.structured_output_schema import JSONObject, build_response_format

TDataObject = TypeVar("TDataObject")
TInputData = TypeVar("TInputData")


class BaseAnalyzer(ABC, Generic[TDataObject, TInputData]):
    """
    基础分析器抽象类
    定义所有分析器的通用接口 and 流程
    """

    def __init__(self, context, config_manager):
        """
        初始化基础分析器

        Args:
            context: AstrBot上下文对象
            config_manager: 配置管理器
        """
        self.context = context
        self.config_manager = config_manager
        # 增量分析模式下的最大数量覆盖值，为 None 时使用配置默认值
        self._incremental_max_count: int | None = None

    def get_provider_id_key(self) -> str | None:
        """
        获取 Provider ID 配置键名
        子类可重写以指定特定的 provider，默认返回 None（使用主 LLM Provider）

        Returns:
            Provider ID 配置键名，如 'topic_provider_id'
        """
        return None

    @abstractmethod
    def get_data_type(self) -> str:
        """
        获取数据类型标识

        Returns:
            数据类型字符串
        """
        pass

    @abstractmethod
    def get_max_count(self) -> int:
        """
        获取最大提取数量

        Returns:
            最大数量
        """
        pass

    @abstractmethod
    def build_prompt(self, data: TInputData) -> str:
        """
        构建LLM提示词

        Args:
            data: 输入数据

        Returns:
            提示词字符串
        """
        pass

    @abstractmethod
    def extract_with_regex(self, result_text: str, max_count: int) -> list[dict]:
        """
        使用正则表达式提取数据

        Args:
            result_text: LLM响应文本
            max_count: 最大提取数量

        Returns:
            提取到的数据列表
        """
        pass

    @abstractmethod
    def create_data_objects(self, data_list: list[dict]) -> list[TDataObject]:
        """
        创建数据对象列表

        Args:
            data_list: 原始数据列表

        Returns:
            数据对象列表
        """
        pass

    def get_response_schema_name(self) -> str:
        return f"{self.get_data_type()}_output"

    def get_response_schema(self) -> JSONObject | None:
        return None

    def get_response_format(self) -> JSONObject | None:
        schema = self.get_response_schema()
        if not schema:
            return None
        return build_response_format(self.get_response_schema_name(), schema)

    def get_schema_retry_max_attempts(self) -> int:
        """
        schema 解析失败后的最大重试次数（不含首轮请求）。
        """
        return 2

    def get_schema_retry_temperatures(
        self, base_temperature: float | None
    ) -> tuple[float, ...]:
        """
        schema 解析失败后的温度重试序列（不含首轮请求）。
        采用动态降温，提高结构化稳定性。
        """
        attempts = max(0, self.get_schema_retry_max_attempts())
        if attempts == 0:
            return ()

        base = base_temperature if base_temperature is not None else 0.7
        first_retry = max(0.1, min(2.0, base * 0.5))

        temperatures: list[float] = [round(first_retry, 2), 0.0]
        if attempts < len(temperatures):
            temperatures = temperatures[:attempts]

        deduped: list[float] = []
        for temp in temperatures:
            if not deduped or deduped[-1] != temp:
                deduped.append(temp)
        return tuple(deduped)

    async def _resolve_provider_temperature(
        self,
        provider_id_key: str | None,
        umo: str | None,
    ) -> float | None:
        """
        尝试从当前将要调用的 Provider 配置中解析基础 temperature。
        """
        provider_id = await get_provider_id_with_fallback(
            self.context,
            self.config_manager,
            provider_id_key,
            umo,
        )
        if not provider_id:
            return None

        provider = self.context.get_provider_by_id(provider_id=provider_id)
        if provider is None:
            return None

        provider_config_obj = getattr(provider, "provider_config", None)
        if not isinstance(provider_config_obj, dict):
            return None

        raw_temperature = provider_config_obj.get("temperature")
        if raw_temperature is None:
            custom_extra_body = provider_config_obj.get("custom_extra_body")
            if isinstance(custom_extra_body, dict):
                raw_temperature = custom_extra_body.get("temperature")

        if isinstance(raw_temperature, bool):
            return None

        parsed_temperature: float | None = None
        if isinstance(raw_temperature, (int, float)):
            parsed_temperature = float(raw_temperature)
        elif isinstance(raw_temperature, str):
            try:
                parsed_temperature = float(raw_temperature.strip())
            except ValueError:
                return None

        if parsed_temperature is None:
            return None

        return max(0.0, min(2.0, parsed_temperature))

    def parse_structured_response(
        self, result_text: str
    ) -> tuple[bool, list[dict] | None, str | None]:
        """
        解析结构化响应（默认 JSON 数组解析）。
        子类可重写此方法定制对象解析逻辑。
        """
        return parse_json_response(result_text, self.get_data_type())

    def build_schema_retry_prompt(
        self,
        original_prompt: str,
        previous_output: str,
        parse_error: str | None,
        attempt_index: int,
    ) -> str:
        """
        构建结构化失败后的修复重试提示词。
        """
        err_text = parse_error or "unknown_parse_error"
        return (
            f"{original_prompt}\n\n"
            "[STRUCTURED OUTPUT RETRY]\n"
            f"Attempt: {attempt_index}\n"
            "Your previous output did not satisfy the required strict JSON schema.\n"
            "Return ONLY valid JSON that strictly matches the schema. "
            "Do not include markdown, explanation, or extra text.\n"
            f"Parse error: {err_text}\n"
            "Previous invalid output:\n"
            f"{previous_output}"
        )

    def _try_parse_with_fallback(
        self, result_text: str
    ) -> tuple[bool, list[dict] | None, str | None]:
        """
        先尝试结构化 JSON 解析（含修复逻辑），失败后立即尝试正则降级。
        """
        success, parsed_data, error_msg = self.parse_structured_response(result_text)
        if success and parsed_data:
            validated_success, validated_data, validated_error = (
                self.validate_parsed_data(parsed_data)
            )
            if validated_success and validated_data:
                return True, validated_data, None
            error_msg = validated_error or error_msg

        regex_data = self.extract_with_regex(result_text, self.get_max_count())
        if regex_data:
            validated_success, validated_data, validated_error = (
                self.validate_parsed_data(regex_data)
            )
            if validated_success and validated_data:
                logger.info(
                    f"{self.get_data_type()}结构化解析失败后，正则降级提取成功，获得 {len(validated_data)} 条数据"
                )
                return True, validated_data, None
            error_msg = validated_error or error_msg

        return False, None, error_msg

    def validate_parsed_data(
        self, data_list: list[dict]
    ) -> tuple[bool, list[dict] | None, str | None]:
        """
        解析结果的本地二次校验（默认直接通过）。
        子类可重写为 Pydantic 校验。
        """
        return True, data_list, None

    def _save_debug_data(self, prompt: str, session_id: str):
        """
        保存调试数据到文件

        Args:
            prompt: 提示词内容
            session_id: 会话ID
        """
        try:
            from pathlib import Path

            from astrbot.api.star import StarTools
            from astrbot.core.utils.astrbot_path import get_astrbot_data_path

            try:
                data_path = StarTools.get_data_dir() / "debug_data"
            except Exception:
                data_path = (
                    Path(get_astrbot_data_path())
                    / "plugin_data"
                    / "astrbot_plugin_qq_group_daily_analysis"
                    / "debug_data"
                )

            data_path.mkdir(parents=True, exist_ok=True)

            file_name = f"{session_id}_{self.get_data_type()}.txt"
            file_path = data_path / file_name

            logger.info(f"正在保存调试数据到: {file_path}")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(prompt)

            logger.info(f"已保存 {self.get_data_type()} 分析 Prompt 到 {file_path}")

        except Exception as e:
            logger.error(f"保存调试数据失败: {e}", exc_info=True)

    def _apply_persona_reinforcement(
        self, prompt: str, system_prompt: str | None
    ) -> str:
        """
        核心的人格强化注入逻辑。采用首尾双重注入（双倍强度）。
        """
        if not system_prompt or not system_prompt.strip():
            return prompt

        logger.info(f"[{self.get_data_type()}分析] 已启用人格设定（首尾双倍强度强化）")
        return (
            f"【角色设定激活】\n你接下来的分析回复必须全程严格保持以下人格设定：\n{system_prompt}\n\n"
            "--- 任务指令与数据开始 ---\n"
            f"{prompt}\n"
            "--- 任务指令与数据结束 ---\n\n"
            f"【再次强制强调：请务必沉浸并以此人设口吻进行输出】\n{system_prompt}，并且严格遵守任务指令部分的要求进行分析输出。"
        )

    async def analyze(
        self, data: TInputData, umo: str | None = None, session_id: str | None = None
    ) -> tuple[list[TDataObject], TokenUsage]:
        """
        统一的分析流程

        Args:
            data: 输入数据
            umo: 模型唯一标识符
            session_id: 会话ID (用于调试模式)

        Returns:
            (分析结果列表, Token使用统计)
        """
        try:
            # 1. 构建提示词
            logger.debug(
                f"{self.get_data_type()}分析开始构建prompt，输入数据类型: {type(data)}"
            )
            data_length = len(data) if isinstance(data, Sized) else "N/A"
            logger.debug(f"{self.get_data_type()}分析输入数据长度: {data_length}")

            prompt = self.build_prompt(data)
            logger.info(f"开始{self.get_data_type()}分析，构建提示词完成")
            logger.debug(
                f"{self.get_data_type()}分析prompt长度: {len(prompt) if prompt else 0}"
            )
            logger.debug(
                f"{self.get_data_type()}分析prompt前100字符: {prompt[:100] if prompt else 'None'}..."
            )

            # 保存调试数据
            debug_mode = self.config_manager.get_debug_mode()
            if debug_mode and session_id and prompt:
                self._save_debug_data(prompt, session_id)
            elif debug_mode and not session_id:
                logger.warning("[Debug] Debug mode enabled but no session_id provided")

            # 检查 prompt 是否为空
            if not prompt or not prompt.strip():
                logger.warning(
                    f"{self.get_data_type()}分析: prompt 为空或只包含空白字符，跳过LLM调用"
                )
                return [], TokenUsage()

            # 2. 调用LLM（使用配置的 provider）
            provider_id_key = self.get_provider_id_key()
            base_temperature = await self._resolve_provider_temperature(
                provider_id_key, umo
            )

            # 获取人格设定
            system_prompt = await self._build_system_prompt(umo)

            # 应用人格强化注入
            prompt = self._apply_persona_reinforcement(prompt, system_prompt)

            logger.info(f"[{self.get_data_type()}分析] 开始发起 LLM 请求, umo: {umo}")

            # [Debug] 记录调试信息
            if debug_mode:
                logger.debug(
                    f"[Debug] debug_mode={debug_mode}, umo={umo}, session_id={session_id}, prompt_len={len(prompt) if prompt else 0}"
                )

            response = await call_provider_with_retry(
                self.context,
                self.config_manager,
                prompt=prompt,
                umo=umo,
                provider_id_key=provider_id_key,
                system_prompt=system_prompt,
                response_format=self.get_response_format(),
            )

            if response is None:
                logger.error(
                    f"{self.get_data_type()}分析调用LLM失败: provider返回None（重试失败）"
                )
                return [], TokenUsage()

            # 3. 提取token使用统计
            token_usage_dict = extract_token_usage(response)
            token_usage = TokenUsage(
                prompt_tokens=token_usage_dict["prompt_tokens"],
                completion_tokens=token_usage_dict["completion_tokens"],
                total_tokens=token_usage_dict["total_tokens"],
            )

            # 4. 提取响应文本
            result_text = extract_response_text(response)
            logger.debug(f"{self.get_data_type()}分析原始响应: {result_text[:500]}...")

            # 5. 尝试结构化解析 + 正则降级解析
            success, parsed_data, error_msg = self._try_parse_with_fallback(result_text)

            # 5.1 仅在两种解析方式都失败时，进入 schema 修复重试（温度递减）
            if not success and self.get_response_format() is not None:
                temperatures = self.get_schema_retry_temperatures(base_temperature)
                for idx, temperature in enumerate(temperatures, start=1):
                    retry_prompt = self.build_schema_retry_prompt(
                        original_prompt=prompt,
                        previous_output=result_text,
                        parse_error=error_msg,
                        attempt_index=idx,
                    )
                    logger.warning(
                        f"{self.get_data_type()}结构化解析失败，触发 schema 修复重试 "
                        f"(attempt={idx}, temperature={temperature:.1f})"
                    )
                    retry_response = await call_provider_with_retry(
                        self.context,
                        self.config_manager,
                        prompt=retry_prompt,
                        umo=umo,
                        provider_id_key=provider_id_key,
                        system_prompt=system_prompt,
                        response_format=self.get_response_format(),
                        extra_generate_kwargs={"temperature": temperature},
                    )
                    if retry_response is None:
                        continue

                    retry_result_text = extract_response_text(retry_response)
                    if not retry_result_text:
                        continue

                    result_text = retry_result_text
                    retry_success, retry_parsed_data, retry_error_msg = (
                        self._try_parse_with_fallback(retry_result_text)
                    )
                    if retry_success:
                        success = True
                        parsed_data = retry_parsed_data
                        error_msg = None
                        break
                    error_msg = retry_error_msg

            if success and parsed_data:
                # JSON解析成功，创建数据对象
                data_objects = self.create_data_objects(parsed_data)
                logger.info(
                    f"{self.get_data_type()}分析成功，解析到 {len(data_objects)} 条数据"
                )
                return data_objects, token_usage

            # 6. 全部尝试失败
            logger.error(
                f"{self.get_data_type()}分析失败: JSON解析与正则降级均未成功: {error_msg}"
            )
            return [], token_usage

        except Exception as e:
            logger.error(f"{self.get_data_type()}分析失败: {e}", exc_info=True)
            return [], TokenUsage()

    async def _build_system_prompt(self, umo: str | None) -> str | None:
        """
        构建带有会话人格的系统提示词，优先级如下：
        1. 插件指定的全局人格 (若核心开关开启)
        2. 会话/对话选定的人格 (若开启了继承开关)
        3. 当前 UMO 的默认人格 (若开启了继承开关)

        Args:
            umo: 用户模型对象标识，用于定位会话上下文

        Returns:
            最终生成的 System Prompt 字符串，若无则返回 None
        """
        # 获取配置
        use_specific = self.config_manager.get_use_plugin_specific_persona()
        specific_id = self.config_manager.get_plugin_specific_persona_id()
        keep_original = self.config_manager.get_keep_original_persona()

        # 获取 AstrBot 核心的人格管理器
        persona_mgr = getattr(self.context, "persona_manager", None)
        if persona_mgr is None:
            return None

        persona_prompt = None

        # --- 优先级 1: 插件指定的全局固定人格 ---
        # 适用于希望所有分析报告都呈现同一种风格的情况
        if use_specific and specific_id:
            try:
                persona_obj = await persona_mgr.get_persona(specific_id)
                persona_prompt = (
                    persona_obj.system_prompt
                    if hasattr(persona_obj, "system_prompt")
                    else None
                )
                if persona_prompt:
                    logger.debug(f"已应用插件指定的全局强制人格设定: {specific_id}")
            except Exception as e:
                logger.warning(f"获取插件指定人格失败 (ID: {specific_id}): {e}")

        # --- 优先级 2: 继承当前会话/群聊的原始人格 ---
        # 只有在未开启“强制人格”且开启了“继承设定”时生效
        if not persona_prompt and keep_original and umo:
            try:
                # 2.1 尝试获取 SharedPreferences 中会话绑定的 Persona ID (通常是 /persona 命令设置的)
                from astrbot.api import sp

                session_service_config = await sp.get_async(
                    scope="umo",
                    scope_id=str(umo),
                    key="session_service_config",
                    default={},
                )
                persona_id = (
                    session_service_config.get("persona_id")
                    if session_service_config
                    else None
                )

                if persona_id and persona_id != "[%None]":
                    persona_obj = await persona_mgr.get_persona(persona_id)
                    persona_prompt = (
                        persona_obj.system_prompt
                        if hasattr(persona_obj, "system_prompt")
                        else None
                    )
                    if persona_prompt:
                        logger.debug(f"继承到会话选定人格: {persona_id}")

                # 2.2 若无会话绑定，尝试获取当前对话(Dialogue)级别的人格
                if not persona_prompt:
                    conv_mgr = getattr(self.context, "conversation_manager", None)
                    if conv_mgr:
                        curr_conv_id = await conv_mgr.get_curr_conversation_id(umo)
                        if curr_conv_id:
                            conv_obj = await conv_mgr.get_conversation(
                                umo, curr_conv_id
                            )
                            if (
                                conv_obj
                                and conv_obj.persona_id
                                and conv_obj.persona_id != "[%None]"
                            ):
                                persona_obj = await persona_mgr.get_persona(
                                    conv_obj.persona_id
                                )
                                persona_prompt = (
                                    persona_obj.system_prompt
                                    if hasattr(persona_obj, "system_prompt")
                                    else None
                                )
                                if persona_prompt:
                                    logger.debug(
                                        f"继承到对话(Dialogue)设定人格: {conv_obj.persona_id}"
                                    )

                # 2.3 若仍无结果，尝试获取 UMO 设定的默认人格
                if not persona_prompt:
                    personality = await persona_mgr.get_default_persona_v3(umo)
                    if isinstance(personality, dict):
                        persona_prompt = personality.get("prompt")
                    else:
                        persona_prompt = getattr(personality, "prompt", None)
                    if persona_prompt:
                        logger.debug("继承到 UMO 默认人格设定")

            except Exception as e:
                logger.warning(f"分析人格回溯识别失败 (umo: {umo}): {e}")

        # 检查生成结果
        if not isinstance(persona_prompt, str) or not persona_prompt.strip():
            return None

        return persona_prompt.strip()
