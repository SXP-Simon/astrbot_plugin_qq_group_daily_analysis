"""
LLM API请求处理工具模块
提供LLM调用和token统计功能
"""

import asyncio
import inspect
import random
import time
from typing import Any

from astrbot.api.provider import LLMResponse
from astrbot.api.star import Context

from ....shared.trace_context import TraceContext
from ....utils.logger import logger
from ....utils.resilience import CircuitBreaker, GlobalRateLimiter
from ...config.config_manager import ConfigManager
from .structured_output_schema import JSONObject, JSONValue

_circuit_breakers = {}
_LLM_LIMITER_INFO_SECONDS = 1.0
_LLM_LIMITER_WARN_SECONDS = 15.0
_LLM_REQUEST_WARN_SECONDS = 120.0
_LLM_REQUEST_STACK_DUMP_SECONDS = 120.0
_LLM_REQUEST_STACK_MAX_DEPTH = 32


def _format_task_await_chain(
    task: asyncio.Task,
    max_depth: int = _LLM_REQUEST_STACK_MAX_DEPTH,
) -> str:
    """格式化异步任务当前 await 链路。

    这里只输出协程的文件、行号与函数名，不读取 frame locals，避免将 prompt、
    API Key 或 Provider 请求参数写入日志。该链路用于定位长时间 LLM 请求到底
    卡在插件、AstrBot Context、Provider SDK 还是 HTTP 客户端层。

    Args:
        task: 正在执行的 asyncio 任务。
        max_depth: 最大追踪层数，避免异常 await 链导致日志过长。

    Returns:
        可直接写入日志的 await 链路描述。
    """
    chain: list[str] = []
    current = task.get_coro()
    seen: set[int] = set()

    truncated = False

    for depth in range(max_depth):
        if current is None:
            break

        current_id = id(current)
        if current_id in seen:
            chain.append("<循环 await 链>")
            break
        seen.add(current_id)

        frame = None
        code = None
        next_awaitable = None

        if inspect.iscoroutine(current):
            frame = current.cr_frame
            code = current.cr_code
            next_awaitable = current.cr_await
        elif inspect.isgenerator(current):
            frame = current.gi_frame
            code = current.gi_code
            next_awaitable = current.gi_yieldfrom
        elif inspect.isasyncgen(current):
            frame = current.ag_frame
            code = current.ag_code
            next_awaitable = current.ag_await
        elif isinstance(current, asyncio.Task):
            next_awaitable = current.get_coro()
            chain.append(
                f"Task(done={current.done()}, cancelled={current.cancelled()})"
            )
            current = next_awaitable
            continue
        else:
            chain.append(type(current).__name__)
            break

        if frame is not None and code is not None:
            chain.append(f"{code.co_filename}:{frame.f_lineno} in {code.co_name}")
        elif code is not None:
            chain.append(f"{code.co_filename}:? in {code.co_name}")
        else:
            chain.append(type(current).__name__)

        current = next_awaitable
        truncated = depth == max_depth - 1 and current is not None

    if not chain:
        return "<无可用 await 链>"
    if truncated:
        chain.append("<await 链已截断>")
    return " -> ".join(chain)


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


def get_provider_circuit_breaker(provider_id: str) -> CircuitBreaker:
    if provider_id not in _circuit_breakers:
        _circuit_breakers[provider_id] = CircuitBreaker(name=f"provider_{provider_id}")
    return _circuit_breakers[provider_id]


_get_circuit_breaker = get_provider_circuit_breaker


async def _call_provider_stream(
    context: Context, provider_id: str, llm_kwargs: dict[str, Any]
) -> LLMResponse:
    provider: Any = context.get_provider_by_id(provider_id=provider_id)
    if provider is None or not hasattr(provider, "text_chat_stream"):
        raise RuntimeError(f"Provider 不存在或不支持流式聊天: {provider_id}")

    stream_kwargs = dict(llm_kwargs)
    stream_kwargs.pop("chat_provider_id", None)

    final_resp = None
    content_parts: list[str] = []
    async for resp in provider.text_chat_stream(**stream_kwargs):
        final_resp = resp
        if getattr(resp, "is_chunk", False):
            text = getattr(resp, "completion_text", "")
            if text:
                content_parts.append(text)

    if final_resp is None:
        raise RuntimeError("流式 LLM 调用未返回任何响应")

    final_text = extract_response_text(final_resp)
    if final_text and not getattr(final_resp, "is_chunk", False):
        return final_resp

    return LLMResponse(
        role="assistant",
        completion_text="".join(content_parts),
        usage=getattr(final_resp, "usage", None),
        raw_completion=getattr(final_resp, "raw_completion", None),
    )


async def _try_get_provider_id_by_id(
    context, provider_id: str, description: str
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
    if not provider_id or not isinstance(provider_id, str) or not provider_id.strip():
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


async def _try_get_session_provider_id(context, umo: str | None) -> str | None:
    """
    尝试获取会话 Provider ID 的辅助函数

    Args:
        context: AstrBot上下文对象
        umo: unified_msg_origin

    Returns:
        Provider ID 或 None
    """
    try:
        # 使用新 API 获取当前会话的 Provider ID
        provider_id = await context.get_current_chat_provider_id(umo=umo)
        if provider_id:
            logger.info(f"✓ 使用当前会话的 Provider: {provider_id}")
            return provider_id
    except Exception as e:
        logger.warning(f"无法获取会话 Provider ID: {e}")
    return None


async def _try_get_first_available_provider_id(context) -> str | None:
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
            trace.metadata.get("override_provider_id") if trace else None
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
            getter_method = f"get_{provider_id_key}"
            if hasattr(config_manager, getter_method):
                specific_provider_id = getattr(config_manager, getter_method)()
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
        or getattr(trace, "group_id", "")
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
            actual_model = None
            actual_provider_type = None
            try:
                # 提取真实 Provider 实例与模型名称以支撑可观测性
                try:
                    provider_inst = context.get_provider_by_id(pid)
                    if provider_inst:
                        prov_cfg = (
                            getattr(provider_inst, "provider_config", None)
                            or getattr(provider_inst, "config", None)
                            or {}
                        )
                        actual_model = (
                            prov_cfg.get("model")
                            or getattr(provider_inst, "model", None)
                            or getattr(provider_inst, "model_id", None)
                        )
                        actual_provider_type = prov_cfg.get("type") or getattr(
                            provider_inst, "provider_type", None
                        )
                except Exception:
                    pass

                if trace:
                    if pid:
                        trace.metadata["provider_id"] = pid
                    if actual_model:
                        trace.metadata["model"] = str(actual_model)
                    prompts_map = trace.metadata.setdefault("llm_prompts", {})
                    if observation_label:
                        slot = prompts_map.setdefault(observation_label, {})
                        slot["provider_id"] = pid
                        if actual_model:
                            slot["model"] = str(actual_model)
                        if actual_provider_type:
                            slot["provider_type"] = str(actual_provider_type)

                llm_kwargs: dict[str, Any] = {
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
                    f"path={call_path}, prompt_len={len(prompt) if prompt else 0}, "
                    f"response_format={r_format is not None}, "
                    f"streaming={enable_streaming_llm_call}"
                )
                if enable_streaming_llm_call:
                    request_task = asyncio.create_task(
                        _call_provider_stream(context, pid, llm_kwargs)
                    )
                else:
                    request_task = asyncio.create_task(
                        context.llm_generate(**llm_kwargs)
                    )

                next_stack_dump_seconds = _LLM_REQUEST_STACK_DUMP_SECONDS
                try:
                    while True:
                        try:
                            resp = await asyncio.wait_for(
                                asyncio.shield(request_task),
                                timeout=_LLM_REQUEST_WARN_SECONDS,
                            )
                            break
                        except TimeoutError:
                            elapsed_seconds = time.monotonic() - request_started_at
                            logger.warning(
                                f"[LLM 调用观测] Provider 请求仍在运行超过 "
                                f"{elapsed_seconds:.0f}s: "
                                f"group={observation_group}, "
                                f"stage={observation_stage}, area={observation_area}, "
                                f"attempt={attempt_num}, "
                                f"fallback={is_fallback_request}, provider={pid}, "
                                f"block_point={call_path}"
                            )
                            if elapsed_seconds >= next_stack_dump_seconds:
                                logger.warning(
                                    f"[LLM 栈观测] Provider 请求 await 链: "
                                    f"group={observation_group}, "
                                    f"stage={observation_stage}, "
                                    f"area={observation_area}, "
                                    f"attempt={attempt_num}, "
                                    f"fallback={is_fallback_request}, "
                                    f"provider={pid}, elapsed={elapsed_seconds:.0f}s, "
                                    f"block_point={call_path}, "
                                    f"await_chain={_format_task_await_chain(request_task)}"
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
                attempts_list.append(attempt_item)
                for s in reversed(trace._spans):
                    if s.get("stage_name") == "LLM_ANALYSIS":
                        s.setdefault("payload", {}).setdefault(
                            "llm_attempts", []
                        ).append(attempt_item)
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
                attempts_list.append(attempt_item)
                for s in reversed(trace._spans):
                    if s.get("stage_name") == "LLM_ANALYSIS":
                        s.setdefault("payload", {}).setdefault(
                            "llm_attempts", []
                        ).append(attempt_item)
                        break
            if r_format is not None and _is_response_format_unsupported_error(err):
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

    for i, (current_pid, is_fallback) in enumerate(attempt_queue):
        attempt_num = i + 1

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

            logger.warning(f"{prefix}请求失败: {last_exc}")
            # 惰性降级：仅当所有 primary provider 的重试都耗尽后才 resolve 并注入 fallback
            if not is_fallback and i == retries - 1 and needs_fallback:
                fallback_provider_id = await get_provider_id_with_fallback(
                    context, config_manager, None, umo
                )
                if (
                    fallback_provider_id
                    and fallback_provider_id != specific_provider_id
                ):
                    for _ in range(retries):
                        attempt_queue.append((fallback_provider_id, True))

            is_last_attempt = i == len(attempt_queue) - 1
            if not is_last_attempt:
                # Exponential backoff with jitter: backoff * (2 ^ (attempt_num - 1)) + random jitter
                sleep_time = backoff * (2 ** (attempt_num - 1)) + random.uniform(0, 1)
                logger.debug(f"等待 {sleep_time:.2f} 秒后重试...")
                await asyncio.sleep(sleep_time)

    logger.error(f"LLM请求队列全部耗尽，最终失败: {last_exc}")
    return None


def extract_token_usage(response) -> dict:
    """
    从LLM响应中提取token使用统计

    Args:
        response: LLM响应对象

    Returns:
        Token使用统计字典，包含prompt_tokens, completion_tokens, total_tokens
    """
    token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    try:
        # 1. 尝试直接获取 response.usage
        usage = getattr(response, "usage", None)

        # 2. 尝试从 response.raw_completion.usage 获取 (兼容旧版)
        if not usage and hasattr(response, "raw_completion"):
            usage = getattr(response.raw_completion, "usage", None)

        # 3. 如果 response 本身就是 dict (某些特殊情况)
        if not usage and isinstance(response, dict):
            usage = response.get("usage")

        if usage:
            # 优先检查 AstrBot 的 TokenUsage 对象字段 (input, output, total)
            # AstrBot TokenUsage define: input (prop), output (attr), total (prop)
            if hasattr(usage, "input") and hasattr(usage, "output"):
                token_usage["prompt_tokens"] = getattr(usage, "input", 0) or 0
                token_usage["completion_tokens"] = getattr(usage, "output", 0) or 0
                token_usage["total_tokens"] = getattr(usage, "total", 0) or 0

            # 处理 usage 是字典的情况
            elif isinstance(usage, dict):
                token_usage["prompt_tokens"] = usage.get("prompt_tokens", 0) or 0
                token_usage["completion_tokens"] = (
                    usage.get("completion_tokens", 0) or 0
                )
                token_usage["total_tokens"] = usage.get("total_tokens", 0) or 0

            # 处理 OpenAI CompletionUsage 等标准对象
            else:
                token_usage["prompt_tokens"] = getattr(usage, "prompt_tokens", 0) or 0
                token_usage["completion_tokens"] = (
                    getattr(usage, "completion_tokens", 0) or 0
                )
                token_usage["total_tokens"] = getattr(usage, "total_tokens", 0) or 0

        return token_usage

    except Exception as e:
        logger.error(f"提取token使用统计失败: {e}")
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def extract_response_text(response) -> str:
    """
    从LLM响应中提取文本内容

    Args:
        response: LLM响应对象

    Returns:
        响应文本内容
    """
    try:
        if hasattr(response, "completion_text"):
            return response.completion_text
        else:
            return str(response)
    except Exception as e:
        logger.error(f"提取响应文本失败: {e}")
        return ""
