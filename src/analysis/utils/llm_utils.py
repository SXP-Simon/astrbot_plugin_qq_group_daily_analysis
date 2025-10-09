"""
LLM API请求处理工具模块
提供LLM调用和token统计功能
"""

import asyncio
from typing import Optional, Any
from astrbot.api import logger
import aiohttp


async def call_provider_with_retry(context, config_manager, prompt: str, max_tokens: int, 
                                 temperature: float, umo: str = None) -> Optional[Any]:
    """
    调用LLM提供者，带超时、重试与退避。支持自定义服务商。
    
    Args:
        context: AstrBot上下文对象
        config_manager: 配置管理器
        prompt: 输入的提示语
        max_tokens: 最大生成token数
        temperature: 采样温度
        umo: 指定使用的模型唯一标识符
        
    Returns:
        LLM生成的结果，失败时返回None
    """
    timeout = config_manager.get_llm_timeout()
    retries = config_manager.get_llm_retries()
    backoff = config_manager.get_llm_backoff()
    
    # 获取自定义服务商参数
    custom_api_key = config_manager.get_custom_api_key()
    custom_api_base = config_manager.get_custom_api_base_url()
    custom_model = config_manager.get_custom_model_name()
    
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            if custom_api_key and custom_api_base and custom_model:
                logger.info(f"使用自定义LLM提供商: {custom_api_base} model={custom_model}")
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Authorization": f"Bearer {custom_api_key}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": custom_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": temperature
                    }
                    aio_timeout = aiohttp.ClientTimeout(total=timeout)
                    async with session.post(custom_api_base, json=payload, headers=headers, timeout=aio_timeout) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            logger.error(f"自定义LLM服务商请求失败: HTTP {resp.status}, 内容: {error_text}")
                        try:
                            response_json = await resp.json()
                        except Exception as json_err:
                            error_text = await resp.text()
                            logger.error(f"自定义LLM服务商响应JSON解析失败: {json_err}, 内容: {error_text}")
                            return None
                        # 兼容 OpenAI 格式，安全访问嵌套字段
                        content = None
                        try:
                            choices = response_json.get("choices")
                            if choices and isinstance(choices, list) and len(choices) > 0:
                                message = choices[0].get("message")
                                if message and isinstance(message, dict):
                                    content = message.get("content")
                            if content is None:
                                logger.error(f"自定义LLM响应格式异常: {response_json}")
                                return None
                        except Exception as key_err:
                            logger.error(f"自定义LLM响应结构解析失败: {key_err}, 响应内容: {response_json}")
                            return None
                        # 构造一个兼容原有逻辑的对象
                        class CustomResponse:
                            completion_text = content
                            raw_completion = response_json
                        return CustomResponse()
            else:
                # 确保使用当前指定的模型
                provider = context.get_using_provider(umo=umo)
                provider_id = 'unknown'
                if provider:
                    try:
                        meta = provider.meta()
                        provider_id = meta.id
                    except Exception as e:
                        logger.debug(f"获取提供商ID失败: {e}")
                logger.info(f"获取到的 provider ID: {provider_id}")
                if not provider or provider_id == 'unknown':
                    logger.warning(f"获取的提供商不正确 (Provider ID: {provider_id})")
                
                logger.info(f"使用LLM provider: {provider}")
                if not provider:
                    logger.error("provider 为空，无法调用 text_chat，直接返回 None")
                    return None
                coro = provider.text_chat(prompt=prompt, max_tokens=max_tokens, temperature=temperature)
                return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError as e:
            last_exc = e
            logger.warning(f"LLM请求超时: 第{attempt}次, timeout={timeout}s")
        except Exception as e:
            last_exc = e
            logger.warning(f"LLM请求失败: 第{attempt}次, 错误: {last_exc}")
        # 若非最后一次，等待退避后重试
        if attempt < retries:
            await asyncio.sleep(backoff * attempt)
    
    # 最终仍失败，记录错误并返回 None 由调用方处理降级，避免抛出异常
    logger.error(f"LLM请求全部重试失败: {last_exc}")
    return None


def extract_token_usage(response) -> Optional[dict]:
    """
    从LLM响应中提取token使用统计
    
    Args:
        response: LLM响应对象
        
    Returns:
        Token使用统计字典，包含prompt_tokens, completion_tokens, total_tokens
    """
    try:
        token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        
        # 安全地提取 usage，避免 response.raw_completion.usage 为 None 导致的 AttributeError
        usage = None
        if getattr(response, 'raw_completion', None) is not None:
            usage = getattr(response.raw_completion, 'usage', None)
            if usage:
                token_usage["prompt_tokens"] = getattr(usage, 'prompt_tokens', 0) or 0
                token_usage["completion_tokens"] = getattr(usage, 'completion_tokens', 0) or 0
                token_usage["total_tokens"] = getattr(usage, 'total_tokens', 0) or 0
        
        return token_usage
        
    except Exception as e:
        logger.error(f"提取token使用统计失败: {e}")
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }


def extract_response_text(response) -> str:
    """
    从LLM响应中提取文本内容
    
    Args:
        response: LLM响应对象
        
    Returns:
        响应文本内容
    """
    try:
        if hasattr(response, 'completion_text'):
            return response.completion_text
        else:
            return str(response)
    except Exception as e:
        logger.error(f"提取响应文本失败: {e}")
        return ""