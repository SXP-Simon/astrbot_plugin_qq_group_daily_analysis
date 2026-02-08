"""
基础分析器抽象类
定义通用分析流程和接口
"""

from abc import ABC, abstractmethod
from typing import Any

from ...models.data_models import TokenUsage
from ...utils.logger import logger
from ..utils.json_utils import parse_json_response
from ..utils.llm_utils import (
    call_provider_with_retry,
    extract_response_text,
    extract_token_usage,
)


class BaseAnalyzer(ABC):
    """
    基础分析器抽象类
    定义所有分析器的通用接口和流程
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

    def get_provider_id_key(self) -> str:
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
    def build_prompt(self, data: Any) -> str:
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
    def create_data_objects(self, data_list: list[dict]) -> list[Any]:
        """
        创建数据对象列表

        Args:
            data_list: 原始数据列表

        Returns:
            数据对象列表
        """
        pass

    def _save_debug_data(self, prompt: str, session_id: str):
        """
        保存调试数据到文件

        Args:
            prompt: 提示词内容
            session_id: 会话ID
        """
        try:
            from pathlib import Path

            from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path

            plugin_name = "astrbot_plugin_qq_group_daily_analysis"
            base_data_path = get_astrbot_plugin_data_path()
            if isinstance(base_data_path, str):
                base_data_path = Path(base_data_path)

            data_path = base_data_path / plugin_name / "debug_data"
            data_path.mkdir(parents=True, exist_ok=True)

            file_name = f"{session_id}_{self.get_data_type()}.txt"
            file_path = data_path / file_name

            logger.info(f"正在保存调试数据到: {file_path}")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(prompt)

            logger.info(f"已保存 {self.get_data_type()} 分析 Prompt 到 {file_path}")

        except Exception as e:
            logger.error(f"保存调试数据失败: {e}", exc_info=True)

    async def analyze(
        self, data: Any, umo: str = None, session_id: str = None
    ) -> tuple[list[Any], TokenUsage]:
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
            logger.debug(
                f"{self.get_data_type()}分析输入数据长度: {len(data) if hasattr(data, '__len__') else 'N/A'}"
            )

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
            logger.info(
                f"[Debug] debug_mode={debug_mode}, session_id={session_id}, prompt_len={len(prompt) if prompt else 0}"
            )  # Added log

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
            max_tokens = self.get_max_tokens()
            temperature = self.get_temperature()
            provider_id_key = self.get_provider_id_key()

            response = await call_provider_with_retry(
                self.context,
                self.config_manager,
                prompt,
                max_tokens,
                temperature,
                umo,
                provider_id_key,
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

            # 5. 尝试JSON解析
            success, parsed_data, error_msg = parse_json_response(
                result_text, self.get_data_type()
            )

            if success and parsed_data:
                # JSON解析成功，创建数据对象
                data_objects = self.create_data_objects(parsed_data)
                logger.info(
                    f"{self.get_data_type()}分析成功，解析到 {len(data_objects)} 条数据"
                )
                return data_objects, token_usage

            # 6. JSON解析失败，使用正则表达式降级
            logger.warning(
                f"{self.get_data_type()}JSON解析失败，尝试正则表达式提取: {error_msg}"
            )
            regex_data = self.extract_with_regex(result_text, self.get_max_count())

            if regex_data:
                logger.info(
                    f"{self.get_data_type()}正则表达式提取成功，获得 {len(regex_data)} 条数据"
                )
                data_objects = self.create_data_objects(regex_data)
                return data_objects, token_usage
            else:
                # 最后的降级方案 - 两种方法都失败
                logger.error(
                    f"{self.get_data_type()}分析失败: JSON解析和正则表达式提取均未成功，返回空列表"
                )
                return [], token_usage

        except Exception as e:
            logger.error(f"{self.get_data_type()}分析失败: {e}", exc_info=True)
            return [], TokenUsage()

    def get_max_tokens(self) -> int:
        """
        获取最大token数，子类可重写

        Returns:
            最大token数
        """
        return 10000

    def get_temperature(self) -> float:
        """
        获取温度参数，子类可重写

        Returns:
            温度参数
        """
        return 0.6
