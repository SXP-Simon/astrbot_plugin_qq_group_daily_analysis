"""
LLM API请求处理工具模块
提供LLM调用和token统计功能
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from astrbot.api.provider import LLMResponse

from ....shared.constants import AnalysisStage
from ....shared.trace_context import TraceContext
from ....utils.logger import logger
from ....utils.resilience import CircuitBreaker, GlobalRateLimiter
from .llm_diagnostics import (
    LLMBlockDiagnosis,
    diagnose_llm_task_block,
    extract_task_await_frames,
    format_task_await_chain,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from astrbot.api.star import Context

    from ....domain.repositories.bot_client_protocol import (
        LLMStreamProviderProtocol,
    )
    from ...config.config_manager import ConfigManager
    from .structured_output_schema import JSONObject, JSONValue

__all__ = [
    "LLMBlockDiagnosis",
    "ProviderMetadata",
    "call_provider_with_retry",
    "diagnose_llm_task_block",
    "extract_response_text",
    "extract_task_await_frames",
    "extract_token_usage",
    "format_task_await_chain",
    "get_provider_id_with_fallback",
]

_circuit_breakers: dict[str, CircuitBreaker] = {}
_LLM_LIMITER_INFO_SECONDS = 1.0
_LLM_LIMITER_WARN_SECONDS = 15.0
_LLM_REQUEST_WARN_SECONDS = 120.0
_LLM_REQUEST_STACK_DUMP_SECONDS = 120.0
_DEFAULT_LLM_HARD_TIMEOUT_SECONDS = 300.0

# 向后兼容内部私有别名
_extract_task_await_frames = extract_task_await_frames
_format_task_await_chain = format_task_await_chain


@dataclass(frozen=True)
class ProviderMetadata:
    """AstrBot Provider 强类型防腐元数据 (ACL)。

    集中收敛对 AstrBot Provider 实例的跨版本反射与兼容探测，
    向业务层提供确定的强类型属性与 IDE F12 跳转支持。

    Attributes:
        provider_id: Provider 唯一标识。
        model: 标准化后的模型名称。
        provider_type: 提供商类型（如 openai/gemini/anthropic）。
        timeout: 提取到的单次请求超时（秒），未配置或无效时为 None。
    """

    provider_id: str
    model: str
    provider_type: str
    timeout: float | None

    @classmethod
    def from_provider_id(cls, context: Context, provider_id: str) -> ProviderMetadata:
        """从 AstrBot Context 与 provider_id 提取标准化 ProviderMetadata。

        Args:
            context: AstrBot 上下文对象。
            provider_id: Provider 唯一标识。

        Returns:
            ProviderMetadata: 强类型元数据值对象。
        """
        if not provider_id:
            return cls(
                provider_id="",
                model="default",
                provider_type="unknown",
                timeout=None,
            )

        try:
            provider_inst = context.get_provider_by_id(provider_id)
        except Exception:
            provider_inst = None

        if provider_inst is None:
            return cls(
                provider_id=provider_id,
                model="default",
                provider_type="unknown",
                timeout=None,
            )

        prov_cfg = (
            getattr(provider_inst, "provider_config", None)
            or getattr(provider_inst, "config", None)
            or {}
        )
        if isinstance(prov_cfg, dict):
            raw_model = (
                prov_cfg.get("model")
                or getattr(provider_inst, "model", None)
                or getattr(provider_inst, "model_id", None)
            )
            raw_type = prov_cfg.get("type") or getattr(
                provider_inst, "provider_type", None
            )
            raw_timeout = prov_cfg.get("timeout")
        else:
            raw_model = getattr(provider_inst, "model", None) or getattr(
                provider_inst, "model_id", None
            )
            raw_type = getattr(provider_inst, "provider_type", None)
            raw_timeout = None

        if raw_timeout is None:
            raw_timeout = getattr(provider_inst, "timeout", None)

        parsed_timeout: float | None = None
        if raw_timeout is not None:
            try:
                t_val = float(raw_timeout)
                if t_val > 0:
                    parsed_timeout = t_val
            except (ValueError, TypeError):
                pass

        return cls(
            provider_id=provider_id,
            model=str(raw_model or "default"),
            provider_type=str(raw_type or "unknown"),
            timeout=parsed_timeout,
        )


_PROVIDER_KEY_GETTERS: dict[str, Callable[[ConfigManager], str]] = {
    "topic_provider_id": lambda cfg: cfg.get_topic_provider_id(),
    "user_title_provider_id": lambda cfg: cfg.get_user_title_provider_id(),
    "golden_quote_provider_id": lambda cfg: cfg.get_golden_quote_provider_id(),
    "quality_provider_id": lambda cfg: cfg.get_quality_provider_id(),
    "drawing_prompt_provider_id": lambda cfg: cfg.get_drawing_prompt_provider_id(),
}


def _is_response_format_unsupported_error(error: Exception) -> bool:
    """
    判断是否为 Provider/网关不支持 response_format 的兼容性错误。
    """
    text = str(error).lower()
    patterns = [
        "response_format",
        "json_schema",
        "unexpected keyword argument",
        "extra fields not permitted",
        "unknown field",
        "not support",
        "not supported",
        "invalid request",
    ]
    return any(pattern in text for pattern in patterns)


def _is_content_risk_error(error: Exception) -> bool:
    """
    判断是否为模型提供商的内容安全审查/敏感词风控拦截 (Content Risk / Moderation Filter)。
    覆盖: DeepSeek (Content Exists Risk), OpenAI/Azure (content_filter), GLM, 通义千问, 百度千帆, 月之暗面, Gemini 等。
    """
    text = str(error).lower()
    patterns = [
        # DeepSeek 典型错误标识
        "content exists risk",
        # OpenAI, Azure 及聚合中转网关标准标识
        "content_filter",
        "content management policy",
        "content_policy_violation",
        "sensitive_words",
        "triggering azure openai",
        # 国内大模型服务商特征（GLM、通义千问、百度千帆、Moonshot）
        "datainspectionfailed",
        "inappropriate content",
        "安全风险",
        "敏感词",
        "安全策略",
        # Gemini 与通用安全评级
        "harm_category",
        "safety rating",
    ]
    return any(pattern in text for pattern in patterns)


def get_provider_circuit_breaker(provider_id: str) -> CircuitBreaker:
    if provider_id not in _circuit_breakers:
        _circuit_breakers[provider_id] = CircuitBreaker(name=f"provider_{provider_id}")
    return _circuit_breakers[provider_id]


_get_circuit_breaker = get_provider_circuit_breaker


async def _call_provider_stream(
    context: Context, provider_id: str, llm_kwargs: dict[str, object]
) -> LLMResponse:
    raw_provider = context.get_provider_by_id(provider_id=provider_id)
    if raw_provider is None or not callable(
        getattr(raw_provider, "text_chat_stream", None)
    ):
        raise RuntimeError(f"Provider 不存在或不支持流式聊天: {provider_id}")
    provider: LLMStreamProviderProtocol = cast(
        "LLMStreamProviderProtocol", raw_provider
    )

    stream_kwargs: dict[str, object] = dict(llm_kwargs)
    stream_kwargs.pop("chat_provider_id", None)

    final_resp = None
    content_parts: list[str] = []
    stream_iter = provider.text_chat_stream(**stream_kwargs)  # pyright: ignore[reportArgumentType]
    async for resp in stream_iter:
        final_resp = resp
        if getattr(resp, "is_chunk", False):
            text = getattr(resp, "completion_text", "")
            if text:
                content_parts.append(text)

    if final_resp is None:
        raise RuntimeError("流式 LLM 调用未返回任何响应")

    final_text = extract_response_text(final_resp)
    if final_text and not getattr(final_resp, "is_chunk", False):
        return (
            final_resp
            if isinstance(final_resp, LLMResponse)
            else LLMResponse(
                role="assistant",
                completion_text=final_text,
                usage=getattr(final_resp, "usage", None),
                raw_completion=getattr(final_resp, "raw_completion", None),
            )
        )

    return LLMResponse(
        role="assistant",
        completion_text="".join(content_parts),
        usage=getattr(final_resp, "usage", None),
        raw_completion=getattr(final_resp, "raw_completion", None),
    )


async def _try_get_provider_id_by_id(
    context: Context, provider_id: str, description: str
) -> str | None:
    """
    尝试通过 ID 获取 Provider ID 的辅助函数

    Args:
        context: AstrBot上下文对象
        provider_id: Provider ID
        description: 描述信息，用于日志

    Returns:
        Provider ID 或 None
    """
    if not provider_id or not provider_id.strip():
        return None

    provider_id = provider_id.strip()
    logger.info(f"尝试使用{description}: {provider_id}")
    try:
        # 验证 Provider 是否存在
        provider = context.get_provider_by_id(provider_id=provider_id)
        if provider:
            logger.info(f"✓ 使用{description}: {provider_id}")
            return provider_id
    except Exception as e:
        logger.warning(f"无法找到{description} '{provider_id}': {e}")
    return None


async def _try_get_session_provider_id(context: Context, umo: str | None) -> str | None:
    """
    尝试获取会话 Provider ID 的辅助函数

    Args:
        context: AstrBot上下文对象
        umo: unified_msg_origin

    Returns:
        Provider ID 或 None
    """
    if not umo:
        return None
    try:
        # 使用新 API 获取当前会话的 Provider ID
        provider_id = await context.get_current_chat_provider_id(umo=umo)
        if provider_id:
            logger.info(f"✓ 使用当前会话的 Provider: {provider_id}")
            return provider_id
    except Exception as e:
        logger.warning(f"无法获取会话 Provider ID: {e}")
    return None


async def _try_get_first_available_provider_id(context: Context) -> str | None:
    """
    尝试获取第一个可用 Provider ID 的辅助函数

    Args:
        context: AstrBot上下文对象

    Returns:
        Provider ID 或 None
    """
    try:
        all_providers = context.get_all_providers()
        if all_providers and len(all_providers) > 0:
            provider = all_providers[0]
            try:
                meta = provider.meta()
                provider_id = meta.id
                logger.info(f"✓ 使用第一个可用 Provider: {provider_id}")
                return provider_id
            except Exception:
                logger.warning("第一个 Provider 无法获取 ID")
    except Exception as e:
        logger.warning(f"无法获取任何 Provider: {e}")
    return None


async def get_provider_id_with_fallback(
    context: Context,
    config_manager: ConfigManager,
    provider_id_key: str | None,
    umo: str | None = None,
) -> str | None:
    """
    根据配置键获取 Provider ID，支持多级回退

    回退顺序：
    1. 尝试从配置获取指定的 provider_id（如 topic_provider_id）
    2. 回退到主 LLM provider_id（llm_provider_id）
    3. 回退到当前会话的 Provider（通过 umo）
    4. 回退到第一个可用的 Provider

    Args:
        context: AstrBot上下文对象
        config_manager: 配置管理器
        provider_id_key: 配置中的 provider_id 键名（如 'topic_provider_id'）
        umo: unified_msg_origin，用于获取会话默认 Provider

    Returns:
        Provider ID 或 None
    """
    try:
        # 输出Provider选择开始日志
        task_desc = provider_id_key if provider_id_key else "默认任务"
        logger.info(f"[Provider 选择] 开始为 {task_desc} 选择 Provider...")

        # 定义回退策略列表
        strategies = []
        strategy_names = []

        # 0. 显式覆盖 Provider (续跑或手动调试时通过 TraceContext 传入)
        trace = TraceContext.current()
        override_provider_id = (
            str(trace.metadata.get("override_provider_id") or "").strip()
            if trace
            else ""
        )
        if override_provider_id:
            strategies.append(
                lambda pid=override_provider_id: _try_get_provider_id_by_id(
                    context, pid, "续跑/手动指定的 Provider"
                )
            )
            strategy_names.append(f"0. 指定的 Provider ({override_provider_id})")

        # 1. 特定任务的 provider_id
        if provider_id_key:
            getter = _PROVIDER_KEY_GETTERS.get(provider_id_key)
            if getter is not None:
                specific_provider_id = getter(config_manager)
            elif hasattr(config_manager, f"get_{provider_id_key}"):
                specific_provider_id = getattr(
                    config_manager, f"get_{provider_id_key}"
                )()
            else:
                specific_provider_id = ""

            if specific_provider_id:
                strategies.append(
                    lambda pid=specific_provider_id: _try_get_provider_id_by_id(
                        context, pid, f"配置的 {provider_id_key}"
                    )
                )
                strategy_names.append(f"1. 配置的 {provider_id_key}")

        # 2. 主 LLM provider_id
        main_provider_id = config_manager.get_llm_provider_id()
        if main_provider_id:
            strategies.append(
                lambda pid=main_provider_id: _try_get_provider_id_by_id(
                    context, pid, "主 LLM Provider"
                )
            )
            strategy_names.append("2. 主 LLM Provider")

        # 3. 当前会话的 Provider
        strategies.append(lambda: _try_get_session_provider_id(context, umo))
        strategy_names.append("3. 当前会话 Provider")

        # 4. 第一个可用的 Provider
        strategies.append(lambda: _try_get_first_available_provider_id(context))
        strategy_names.append("4. 第一个可用 Provider")

        # 输出回退策略列表
        logger.info(f"[Provider 选择] 回退策略顺序：{' -> '.join(strategy_names)}")

        # 依次尝试每个策略
        for idx, strategy in enumerate(strategies):
            provider_id = await strategy()
            if provider_id:
                logger.info(
                    f"[Provider 选择] ✓ 成功！使用策略 #{idx + 1}，Provider ID: {provider_id}"
                )
                return provider_id

        logger.error("[Provider 选择] ✗ 失败：所有回退策略均无法获取可用 Provider")
        return None

    except Exception as e:
        logger.error(f"[Provider 选择] ✗ 异常：Provider 选择过程出错: {e}")
        return None


async def call_provider_with_retry(
    context: Context,
    config_manager: ConfigManager,
    prompt: str,
    umo: str | None = None,
    provider_id_key: str | None = None,
    provider_id: str | None = None,
    system_prompt: str | None = None,
    response_format: JSONObject | None = None,
    extra_generate_kwargs: dict[str, JSONValue] | None = None,
    observation_label: str | None = None,
) -> LLMResponse | None:
    """
    调用LLM提供者，带超时、重试与退避。支持自定义服务商和配置化 Provider 选择。

    Args:
        context: AstrBot上下文对象
        config_manager: 配置管理器
        prompt: 输入的提示语
        umo: 指定使用的模型唯一标识符
        provider_id_key: 配置中的 provider_id 键名（如 'topic_provider_id'），用于选择特定的 Provider
        system_prompt: 系统提示词
        response_format: 结构化输出约束（OpenAI 风格）
        extra_generate_kwargs: 传递给 context.llm_generate 的附加参数（用于内部高级重试策略）
        observation_label: 本次调用所属的业务区域标签，用于日志追踪具体分析器。

    Returns:
        LLM生成的结果，失败时返回None
    """
    # 注意: 超时由 AstrBot Provider 内部配置控制，不再使用插件层 asyncio.wait_for
    # 用户可在 AstrBot WebUI 中为每个 Provider 配置 timeout 参数
    retries = config_manager.get_llm_retries()
    backoff = config_manager.get_llm_backoff()
    enable_streaming_llm_call = config_manager.get_enable_streaming_llm_call()
    trace = TraceContext.current()
    trace_metadata = trace.metadata if trace else {}
    observation_stage = str(trace_metadata.get("llm_stage") or "unknown")
    observation_group = str(
        trace_metadata.get("llm_group_id")
        or (trace.group_id if trace else "")
        or "unknown"
    )
    observation_area = observation_label or provider_id_key or "未标注"

    # 1. 确定我们要尝试的 Provider 队列
    attempt_queue = []

    # 尝试获取指定的 Provider
    specific_provider_id = provider_id
    if not specific_provider_id:
        specific_provider_id = await get_provider_id_with_fallback(
            context, config_manager, provider_id_key, umo
        )
    if specific_provider_id:
        attempt_queue.extend([(specific_provider_id, False)] * retries)

    if not attempt_queue:
        logger.error("无可用 Provider，无法调用 llm_generate")
        return None

    # 2. 核心请求执行闭包
    async def _execute_llm_request(
        pid: str,
        r_format: JSONObject | None,
        attempt_num: int,
        is_fallback_request: bool,
    ) -> LLMResponse:
        request_started_at = time.monotonic()
        actual_model = None
        cb = _get_circuit_breaker(pid)
        if not cb.allow_request():
            logger.warning(f"Provider {pid} 熔断器已打开，跳过本次请求")
            raise Exception("Circuit breaker open")

        try:
            limiter = GlobalRateLimiter.get_instance()
            semaphore = limiter.semaphore
            wait_started_at = time.monotonic()
            logger.debug(
                f"[LLM 限流观测] 等待全局 Provider 槽位: "
                f"group={observation_group}, stage={observation_stage}, "
                f"area={observation_area}, attempt={attempt_num}, "
                f"fallback={is_fallback_request}, provider={pid}, "
                f"available={limiter.available_slots}/{limiter.max_concurrency}"
            )
            while True:
                try:
                    await asyncio.wait_for(
                        semaphore.acquire(), timeout=_LLM_LIMITER_WARN_SECONDS
                    )
                    break
                except TimeoutError:
                    logger.warning(
                        f"[LLM 限流观测] 等待全局 Provider 槽位超过 "
                        f"{time.monotonic() - wait_started_at:.0f}s: "
                        f"group={observation_group}, stage={observation_stage}, "
                        f"area={observation_area}, attempt={attempt_num}, "
                        f"fallback={is_fallback_request}, provider={pid}, "
                        f"available={limiter.available_slots}/"
                        f"{limiter.max_concurrency}"
                    )

            waited_seconds = time.monotonic() - wait_started_at
            log_method = (
                logger.info
                if waited_seconds >= _LLM_LIMITER_INFO_SECONDS
                else logger.debug
            )
            log_method(
                f"[LLM 限流观测] 已取得全局 Provider 槽位: "
                f"group={observation_group}, stage={observation_stage}, "
                f"area={observation_area}, attempt={attempt_num}, "
                f"fallback={is_fallback_request}, provider={pid}, "
                f"wait={waited_seconds:.2f}s, available={limiter.available_slots}/"
                f"{limiter.max_concurrency}"
            )
            request_started_at = time.monotonic()
            try:
                # 借助强类型 ProviderMetadata (ACL) 提取模型与超时信息
                meta = ProviderMetadata.from_provider_id(context, pid)
                actual_model = meta.model
                actual_provider_type = meta.provider_type

                # 解析硬超时参数与来源
                configured_hard_timeout = (
                    config_manager.get_llm_hard_timeout()
                    if hasattr(config_manager, "get_llm_hard_timeout")
                    else 0
                )
                if configured_hard_timeout > 0:
                    effective_timeout = float(configured_hard_timeout)
                    timeout_source = (
                        f"插件配置 (llm_hard_timeout={configured_hard_timeout}s)"
                    )
                elif meta.timeout is not None:
                    effective_timeout = meta.timeout
                    timeout_source = f"Provider 配置 (timeout={meta.timeout:g}s)"
                else:
                    effective_timeout = _DEFAULT_LLM_HARD_TIMEOUT_SECONDS
                    timeout_source = (
                        f"默认安全兜底 ({_DEFAULT_LLM_HARD_TIMEOUT_SECONDS:.0f}s, "
                        "未检测到 Provider timeout 配置)"
                    )

                logger.info(
                    f"[LLM 超时配置] 本次请求硬超时上限: {effective_timeout:.1f}s | "
                    f"来源: {timeout_source} | provider={pid}, group={observation_group}, "
                    f"stage={observation_stage}, area={observation_area}, attempt={attempt_num}"
                )

                if trace:
                    if pid:
                        trace.metadata["provider_id"] = pid
                    if actual_model:
                        trace.metadata["model"] = str(actual_model)
                    prompts_map = trace.metadata.setdefault("llm_prompts", {})
                    if isinstance(prompts_map, dict) and observation_label:
                        slot = prompts_map.setdefault(observation_label, {})
                        if isinstance(slot, dict):
                            slot["provider_id"] = pid
                            if actual_model:
                                slot["model"] = str(actual_model)
                            if actual_provider_type:
                                slot["provider_type"] = str(actual_provider_type)

                llm_kwargs: dict[str, object] = {
                    "chat_provider_id": pid,
                    "prompt": prompt,
                }
                if system_prompt is not None:
                    llm_kwargs["system_prompt"] = system_prompt
                if r_format is not None:
                    llm_kwargs["response_format"] = r_format
                if extra_generate_kwargs:
                    llm_kwargs.update(extra_generate_kwargs)

                call_path = (
                    "provider.text_chat_stream"
                    if enable_streaming_llm_call
                    else "context.llm_generate"
                )
                logger.info(
                    f"[LLM 调用观测] 开始 Provider 请求: "
                    f"group={observation_group}, stage={observation_stage}, "
                    f"area={observation_area}, attempt={attempt_num}, "
                    f"fallback={is_fallback_request}, provider={pid}, "
                    f"path={call_path}, timeout={effective_timeout:.1f}s, "
                    f"prompt_len={len(prompt) if prompt else 0}, "
                    f"response_format={r_format is not None}, "
                    f"streaming={enable_streaming_llm_call}"
                )
                if enable_streaming_llm_call:
                    request_task = asyncio.create_task(
                        _call_provider_stream(context, pid, llm_kwargs)
                    )
                else:
                    llm_call_params: dict[str, object] = {
                        "chat_provider_id": pid,
                        "prompt": prompt,
                        "system_prompt": system_prompt,
                    }
                    if r_format is not None:
                        llm_call_params["response_format"] = r_format
                    if extra_generate_kwargs:
                        llm_call_params.update(extra_generate_kwargs)

                    request_task = asyncio.create_task(
                        context.llm_generate(**llm_call_params)  # pyright: ignore[reportArgumentType]
                    )

                next_stack_dump_seconds = _LLM_REQUEST_STACK_DUMP_SECONDS
                try:
                    while True:
                        elapsed_seconds = time.monotonic() - request_started_at
                        remaining_timeout = effective_timeout - elapsed_seconds
                        if remaining_timeout <= 0:
                            diagnosis = diagnose_llm_task_block(
                                request_task,
                                elapsed_seconds,
                                default_block_point=call_path,
                                is_timeout_aborted=True,
                            )
                            logger.error(
                                f"[LLM 硬超时截断] {diagnosis.status_title}: "
                                f"group={observation_group}, stage={observation_stage}, "
                                f"area={observation_area}, attempt={attempt_num}, "
                                f"fallback={is_fallback_request}, provider={pid}, "
                                f"elapsed={elapsed_seconds:.1f}s >= limit={effective_timeout:.1f}s ({timeout_source}), "
                                f"block_point={diagnosis.block_point} | "
                                f"排查提示: {diagnosis.guidance_hint}"
                            )
                            if not request_task.done():
                                request_task.cancel()
                                try:
                                    await request_task
                                except (asyncio.CancelledError, Exception):
                                    pass
                            raise TimeoutError(
                                f"LLM 请求超过硬超时上限 ({effective_timeout:.1f}s, 来源: {timeout_source}), 已主动截断连接"
                            )

                        slice_timeout = min(
                            _LLM_REQUEST_WARN_SECONDS, remaining_timeout
                        )
                        try:
                            resp = await asyncio.wait_for(
                                asyncio.shield(request_task),
                                timeout=slice_timeout,
                            )
                            break
                        except TimeoutError:
                            elapsed_seconds = time.monotonic() - request_started_at
                            if elapsed_seconds >= effective_timeout:
                                continue

                            diagnosis = diagnose_llm_task_block(
                                request_task,
                                elapsed_seconds,
                                default_block_point=call_path,
                            )
                            logger.warning(
                                f"[LLM 阻塞诊断] {diagnosis.status_title}: "
                                f"group={observation_group}, "
                                f"stage={observation_stage}, area={observation_area}, "
                                f"attempt={attempt_num}, "
                                f"fallback={is_fallback_request}, provider={pid}, "
                                f"elapsed={elapsed_seconds:.0f}s / limit={effective_timeout:.0f}s, "
                                f"block_point={diagnosis.block_point} | "
                                f"提示: {diagnosis.guidance_hint}"
                            )
                            if not diagnosis.is_known:
                                logger.warning(
                                    f"[LLM 栈观测] Provider 请求 await 链: "
                                    f"group={observation_group}, "
                                    f"stage={observation_stage}, "
                                    f"area={observation_area}, "
                                    f"attempt={attempt_num}, "
                                    f"fallback={is_fallback_request}, "
                                    f"provider={pid}, elapsed={elapsed_seconds:.0f}s, "
                                    f"block_point={diagnosis.block_point}, "
                                    f"await_chain={diagnosis.await_chain}"
                                )
                            else:
                                if elapsed_seconds >= next_stack_dump_seconds:
                                    logger.debug(
                                        f"[LLM 栈观测] Provider 请求 await 链 (已知状态 {diagnosis.state}): "
                                        f"group={observation_group}, area={observation_area}, "
                                        f"await_chain={diagnosis.await_chain}"
                                    )
                                    next_stack_dump_seconds *= 2
                except asyncio.CancelledError:
                    if not request_task.done():
                        request_task.cancel()
                    raise

                logger.info(
                    f"[LLM 调用观测] Provider 请求完成: "
                    f"group={observation_group}, stage={observation_stage}, "
                    f"area={observation_area}, attempt={attempt_num}, "
                    f"fallback={is_fallback_request}, provider={pid}, "
                    f"duration={time.monotonic() - request_started_at:.2f}s, "
                    f"path={call_path}"
                )
            finally:
                semaphore.release()
                logger.debug(
                    f"[LLM 限流观测] 已释放全局 Provider 槽位: "
                    f"group={observation_group}, stage={observation_stage}, "
                    f"area={observation_area}, attempt={attempt_num}, "
                    f"fallback={is_fallback_request}, provider={pid}, "
                    f"duration={time.monotonic() - request_started_at:.2f}s, "
                    f"available={limiter.available_slots}/{limiter.max_concurrency}"
                )
            cb.record_success()
            duration_ms = (time.monotonic() - request_started_at) * 1000
            if trace:
                attempts_list = trace.metadata.setdefault("llm_attempts", [])
                attempt_item = {
                    "area": observation_area,
                    "attempt": attempt_num,
                    "provider_id": pid,
                    "model": actual_model or "default",
                    "status": "success",
                    "duration_ms": round(duration_ms, 1),
                    "is_fallback": is_fallback_request,
                }
                if isinstance(attempts_list, list):
                    attempts_list.append(attempt_item)
                for s in reversed(trace._spans):
                    if s.get("stage_name") == AnalysisStage.LLM_ANALYSIS.value:
                        payload = s.setdefault("payload", {})
                        span_attempts = payload.setdefault("llm_attempts", [])
                        if isinstance(span_attempts, list):
                            span_attempts.append(attempt_item)
                        break
            return resp
        except Exception as err:
            duration_ms = (time.monotonic() - request_started_at) * 1000
            if trace:
                attempts_list = trace.metadata.setdefault("llm_attempts", [])
                attempt_item = {
                    "area": observation_area,
                    "attempt": attempt_num,
                    "provider_id": pid,
                    "model": actual_model or "default",
                    "status": "failed",
                    "duration_ms": round(duration_ms, 1),
                    "is_fallback": is_fallback_request,
                    "error": str(err),
                }
                if isinstance(attempts_list, list):
                    attempts_list.append(attempt_item)
                for s in reversed(trace._spans):
                    if s.get("stage_name") == AnalysisStage.LLM_ANALYSIS.value:
                        payload = s.setdefault("payload", {})
                        span_attempts = payload.setdefault("llm_attempts", [])
                        if isinstance(span_attempts, list):
                            span_attempts.append(attempt_item)
                        break
            if r_format is not None and _is_response_format_unsupported_error(err):
                raise err
            if _is_content_risk_error(err):
                logger.debug(
                    f"[LLM 熔断保护] 请求命中了上游内容风控拦截，不计入 Provider[{pid}] 熔断器失败计数。"
                )
                raise err
            cb.record_failure()
            raise err

    # 3. 开始执行队列
    last_exc = None
    current_response_format = response_format

    # 记录上一次尝试的 Provider ID，用于判断是否发生切换
    previous_pid = None
    # 惰性降级标记：仅在 primary provider 重试用尽后才 resolve fallback
    needs_fallback = provider_id_key is not None

    queue_index = 0
    while queue_index < len(attempt_queue):
        current_pid, is_fallback = attempt_queue[queue_index]
        attempt_num = queue_index + 1

        # 修复状态污染：如果切换了全新的 Provider，必须重置 response_format 约束
        if current_pid != previous_pid:
            current_response_format = response_format
        previous_pid = current_pid

        prefix = "[降级补偿] " if is_fallback else "[LLM 调用] "
        logger.info(
            f"{prefix}尝试 #{attempt_num} | Provider ID: {current_pid} | "
            f"stage={observation_stage} | area={observation_area} | "
            f"prompt长度={len(prompt) if prompt else 0}字符"
        )

        if not prompt or not prompt.strip():
            logger.error("LLM provider: prompt 为空，无法调用")
            return None

        try:
            return await _execute_llm_request(
                current_pid,
                current_response_format,
                attempt_num,
                is_fallback,
            )

        except Exception as e:
            last_exc = e

            # 处理不支持 response_format 的情况
            if (
                current_response_format is not None
                and _is_response_format_unsupported_error(e)
            ):
                logger.warning(
                    f"{prefix}当前 Provider 可能不支持 response_format，已自动降级为无 schema 约束。"
                )
                current_response_format = None
                # 在当前尝试额度内立即再试一次剥离了 schema 的请求
                try:
                    return await _execute_llm_request(
                        current_pid,
                        current_response_format,
                        attempt_num,
                        is_fallback,
                    )
                except Exception as inner_e:
                    last_exc = inner_e

            # 处理上游内容安全审查/敏感词风控拦截 (Content Risk / Moderation Filter)
            if _is_content_risk_error(last_exc):
                logger.warning(
                    f"{prefix}[LLM 内容风控拦截] 上游模型服务商触发了安全审查拒绝 (Content Risk / Moderation Filter)！\n"
                    f"  - 错误详情: {last_exc}\n"
                    f"  - 影响说明: 当前 Provider [{current_pid}] 无法处理含有受限/敏感词的群聊上下文，已快速短路跳过当前模型的重复重试。\n"
                    f"  - 排查与解决建议:\n"
                    f"    1. 更换为安全审核策略更宽松、中立或本地部署的模型 (如 Ollama / 海外模型)，并配置备用 Provider；\n"
                    f"    2. 为当前分析模型配置学术研究/客观数据观察者视角的分析人格 (Persona) 或 Jailbreak 提示词；\n"
                    f"    3. 检查并适当调整分析提示词模板 (Prompt)，避免出现易被上游安全审查误杀的引导词；\n"
                    f"    4. 在插件设置中配置群消息过滤词，过滤群内特定违规发言。"
                )

                # 惰性降级：若主 Provider 遭遇风控且存在未注入的 fallback，立即注入 fallback 并切换
                if not is_fallback and needs_fallback:
                    fallback_provider_id = await get_provider_id_with_fallback(
                        context, config_manager, None, umo
                    )
                    if (
                        fallback_provider_id
                        and fallback_provider_id != specific_provider_id
                    ):
                        needs_fallback = False
                        # 剔除当前主 Provider 的所有后续同质重试
                        attempt_queue = [
                            item
                            for idx, item in enumerate(attempt_queue)
                            if idx <= queue_index or item[0] != current_pid
                        ]
                        for _ in range(retries):
                            attempt_queue.append((fallback_provider_id, True))
                        queue_index += 1
                        continue

                # 若无 fallback 或 fallback 同样遭遇风控，立即跳过所有属于当前 Provider 的重试
                attempt_queue = [
                    item
                    for idx, item in enumerate(attempt_queue)
                    if idx <= queue_index or item[0] != current_pid
                ]
                queue_index += 1
                continue

            logger.warning(f"{prefix}请求失败: {last_exc}")
            # 惰性降级：仅当所有 primary provider 的重试都耗尽后才 resolve 并注入 fallback
            if not is_fallback and queue_index == retries - 1 and needs_fallback:
                fallback_provider_id = await get_provider_id_with_fallback(
                    context, config_manager, None, umo
                )
                if (
                    fallback_provider_id
                    and fallback_provider_id != specific_provider_id
                ):
                    for _ in range(retries):
                        attempt_queue.append((fallback_provider_id, True))

            is_last_attempt = queue_index == len(attempt_queue) - 1
            if not is_last_attempt:
                # Exponential backoff with jitter: backoff * (2 ^ (attempt_num - 1)) + random jitter
                sleep_time = backoff * (2 ** (attempt_num - 1)) + random.uniform(0, 1)
                logger.debug(f"等待 {sleep_time:.2f} 秒后重试...")
                await asyncio.sleep(sleep_time)

            queue_index += 1

    logger.error(f"LLM请求队列全部耗尽，最终失败: {last_exc}")
    return None


def extract_token_usage(response: object) -> dict[str, int]:
    """从LLM响应中提取token使用统计 (委托 Domain TokenUsage ACL)。

    Args:
        response: LLM响应对象

    Returns:
        Token使用统计字典，包含prompt_tokens, completion_tokens, total_tokens
    """
    from ....domain.value_objects import TokenUsage

    usage_vo = TokenUsage.from_llm_response(response)
    return {
        "prompt_tokens": usage_vo.prompt_tokens,
        "completion_tokens": usage_vo.completion_tokens,
        "total_tokens": usage_vo.total_tokens,
    }


def extract_response_text(response: object) -> str:
    """从LLM响应中提取文本内容 (ACL 防腐)。

    Args:
        response: LLM响应对象

    Returns:
        响应文本内容
    """
    if response is None:
        return ""
    if isinstance(response, LLMResponse):
        return response.completion_text or ""
    try:
        text = getattr(response, "completion_text", None)
        if text is not None:
            return str(text)
        return str(response)
    except Exception as e:
        logger.error(f"提取响应文本失败: {e}")
        return ""
