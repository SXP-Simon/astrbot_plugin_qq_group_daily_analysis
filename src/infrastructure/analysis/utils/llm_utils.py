"""
LLM API请求处理工具模块
提供LLM调用和token统计功能
"""

import asyncio
from typing import Any

from ....utils.logger import logger
from ....utils.resilience import CircuitBreaker, global_llm_rate_limiter

_circuit_breakers = {}


def _get_circuit_breaker(provider_id: str) -> CircuitBreaker:
    if provider_id not in _circuit_breakers:
        _circuit_breakers[provider_id] = CircuitBreaker(name=f"provider_{provider_id}")
    return _circuit_breakers[provider_id]


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


async def _try_get_session_provider_id(context, umo: str) -> str | None:
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
    context, config_manager, provider_id_key: str, umo: str = None
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
    context,
    config_manager,
    prompt: str,
    max_tokens: int,
    temperature: float,
    umo: str = None,
    provider_id_key: str = None,
) -> Any | None:
    """
    调用LLM提供者，带超时、重试与退避。支持自定义服务商和配置化 Provider 选择。

    Args:
        context: AstrBot上下文对象
        config_manager: 配置管理器
        prompt: 输入的提示语
        max_tokens: 最大生成token数
        temperature: 采样温度
        umo: 指定使用的模型唯一标识符
        provider_id_key: 配置中的 provider_id 键名（如 'topic_provider_id'），用于选择特定的 Provider

    Returns:
        LLM生成的结果，失败时返回None
    """
    # 注意: 超时由 AstrBot Provider 内部配置控制，不再使用插件层 asyncio.wait_for
    # 用户可在 AstrBot WebUI 中为每个 Provider 配置 timeout 参数
    retries = config_manager.get_llm_retries()
    backoff = config_manager.get_llm_backoff()

    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            # 使用新的 provider 选择逻辑，获取 Provider ID
            provider_id = await get_provider_id_with_fallback(
                context, config_manager, provider_id_key, umo
            )

            if not provider_id:
                logger.error("provider_id 为空，无法调用 llm_generate，直接返回 None")
                return None

            logger.info(
                f"[LLM 调用] 使用 Provider ID: {provider_id} | "
                f"max_tokens={max_tokens} | temperature={temperature} | "
                f"prompt长度={len(prompt) if prompt else 0}字符"
            )

            logger.debug(
                f"[LLM 调用] Prompt 前100字符: {prompt[:100] if prompt else 'None'}..."
            )

            # 检查 prompt 是否为空
            if not prompt or not prompt.strip():
                logger.error(
                    "LLM provider: prompt 为空或只包含空白字符，无法调用 llm_generate"
                )
                return None

            # 获取熔断器
            cb = _get_circuit_breaker(provider_id)
            if not cb.allow_request():
                logger.warning(f"Provider {provider_id} 熔断器已打开，跳过本次请求")
                return None

            # 使用全局限流器 + 熔断器记录
            # 超时由 Provider 内部控制，无需外层 wait_for
            try:
                async with global_llm_rate_limiter:
                    llm_resp = await context.llm_generate(
                        chat_provider_id=provider_id,
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )

                # 成功记录
                cb.record_success()
                return llm_resp

            except Exception as e:
                # 失败记录
                cb.record_failure()
                raise e

        except asyncio.TimeoutError as e:
            last_exc = e
            logger.warning(f"LLM请求超时: 第{attempt}次 (Provider 内部超时)")
        except Exception as e:
            last_exc = e
            logger.warning(f"LLM请求失败: 第{attempt}次, 错误: {last_exc}")
        # 若非最后一次，等待退避后重试
        if attempt < retries:
            await asyncio.sleep(backoff * attempt)

    # 最终仍失败，记录错误并返回 None 由调用方处理降级，避免抛出异常
    logger.error(f"LLM请求全部重试失败: {last_exc}")
    return None


def extract_token_usage(response) -> dict | None:
    """
    从LLM响应中提取token使用统计

    Args:
        response: LLM响应对象

    Returns:
        Token使用统计字典，包含prompt_tokens, completion_tokens, total_tokens
    """
    try:
        token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # 尝试从 LLMResponse 中提取 usage
        # 假设 LLMResponse 有 usage 属性或 raw_completion 属性
        if hasattr(response, "usage") and response.usage:
            usage = response.usage
            token_usage["prompt_tokens"] = getattr(usage, "prompt_tokens", 0) or 0
            token_usage["completion_tokens"] = (
                getattr(usage, "completion_tokens", 0) or 0
            )
            token_usage["total_tokens"] = getattr(usage, "total_tokens", 0) or 0
            return token_usage

        # 兼容旧的提取方式 (如果 response 是旧的 ProviderResponse)
        if getattr(response, "raw_completion", None) is not None:
            usage = getattr(response.raw_completion, "usage", None)
            if usage:
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
