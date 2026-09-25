"""
LLM 异步任务调用栈与长时间阻塞诊断模块
负责从正在执行的 asyncio.Task 中提取调用链路、识别具体阻塞阶段（限流排队、退避重试、网络握手、上游推理等）。
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass

_LLM_REQUEST_STACK_MAX_DEPTH = 32


@dataclass
class LLMBlockDiagnosis:
    """LLM 任务长时间阻塞点的结构化诊断结果。

    Attributes:
        state: 阻塞状态枚举标识（如 'RATE_LIMIT_QUEUE', 'SDK_RETRY_BACKOFF', 'CONNECTING_NETWORK', 'WAITING_UPSTREAM_RESPONSE', 'UNKNOWN'）。
        status_title: 用户友好的诊断状态标题。
        guidance_hint: 针对该阻塞点的排查与优化引导文案。
        is_known: 是否匹配到已知模式。
        await_chain: 格式化后的 await 协程调用链路字符串。
        block_point: 业务层面的阻塞打点标记。
    """

    state: str
    status_title: str
    guidance_hint: str
    is_known: bool
    await_chain: str
    block_point: str


@dataclass
class _TaskAwaitFrame:
    """异步任务调用链路中的单个调用帧元数据。"""

    filename: str
    lineno: int | None
    func_name: str
    target_type: str


def extract_task_await_frames(
    task: asyncio.Task,
    max_depth: int = _LLM_REQUEST_STACK_MAX_DEPTH,
) -> list[_TaskAwaitFrame]:
    """提取异步任务当前 await 链路的结构化调用帧列表。

    从 task.get_coro() 开始逐层遍历 cr_await / gi_yieldfrom / ag_await，
    获取完整的调用链路帧，仅保留文件名、行号与函数名，绝不读取 frame locals。

    Args:
        task: 目标异步任务。
        max_depth: 最大追溯深度，防止深层递归。

    Returns:
        调用帧元数据列表。
    """
    frames: list[_TaskAwaitFrame] = []
    current = task.get_coro()
    seen: set[int] = set()

    for _ in range(max_depth):
        if current is None:
            break

        current_id = id(current)
        if current_id in seen:
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
            frames.append(
                _TaskAwaitFrame(
                    filename="<Task>",
                    lineno=None,
                    func_name="Task",
                    target_type=type(current).__name__,
                )
            )
            current = next_awaitable
            continue
        else:
            frames.append(
                _TaskAwaitFrame(
                    filename="<Awaitable>",
                    lineno=None,
                    func_name=type(current).__name__,
                    target_type=type(current).__name__,
                )
            )
            break

        if code is not None:
            frames.append(
                _TaskAwaitFrame(
                    filename=code.co_filename,
                    lineno=frame.f_lineno if frame is not None else None,
                    func_name=code.co_name,
                    target_type=type(current).__name__,
                )
            )
        else:
            frames.append(
                _TaskAwaitFrame(
                    filename="<Unknown>",
                    lineno=None,
                    func_name=type(current).__name__,
                    target_type=type(current).__name__,
                )
            )

        current = next_awaitable

    return frames


def format_task_await_chain(
    task: asyncio.Task,
    max_depth: int = _LLM_REQUEST_STACK_MAX_DEPTH,
) -> str:
    """格式化异步任务当前 await 链路。

    这里只输出协程的文件、行号与函数名，不读取 frame locals，避免将 prompt、
    API Key 或 Provider 请求参数写入日志。

    Args:
        task: 正在执行的 asyncio 任务。
        max_depth: 最大追踪层数，避免异常 await 链导致日志过长。

    Returns:
        可直接写入日志的 await 链路描述。
    """
    frames = extract_task_await_frames(task, max_depth)
    if not frames:
        return "<无可用 await 链>"
    formatted = [
        f"{f.filename}:{f.lineno or '?'} in {f.func_name}"
        if f.filename not in ("<Task>", "<Awaitable>", "<Unknown>")
        else f.func_name
        for f in frames
    ]
    return " -> ".join(formatted)


def diagnose_llm_task_block(
    task: asyncio.Task | None,
    elapsed_seconds: float,
    default_block_point: str = "context.llm_generate",
) -> LLMBlockDiagnosis:
    """分析长时间运行的 LLM 任务阻塞点并生成对用户友好的结构化诊断信息。

    基于 AstrBot 核心 Provider 调用链（ProviderManager / request_retry / OpenAI / Anthropic / Gemini / httpx）
    的具体协程栈特征进行逐层分类：
    1. 全局限流排队（RateLimiter / Semaphore acquire 等待中）
    2. SDK 故障退避重试（request_retry / tenacity 在异常后处于退避 sleep 中）
    3. 网络建连阻塞（TCP / SSL 握手 / DNS 解析中）
    4. 大模型上游响应等待（HTTP 连接已就绪，服务端推理生成或流式传输中）
    5. 未知阻塞点（安全回退，输出完整 await 链）

    Args:
        task: 当前执行中的异步任务。
        elapsed_seconds: 当前请求已消耗的秒数。
        default_block_point: 默认的业务阻塞路径。

    Returns:
        LLMBlockDiagnosis: 结构化诊断对象。
    """
    if task is None:
        return LLMBlockDiagnosis(
            state="UNKNOWN",
            status_title="⚠️ Provider 请求仍在运行 (未知阻塞点)",
            guidance_hint=f"请求正在执行中（已耗时 {elapsed_seconds:.0f}s），未获取到有效任务句柄。",
            is_known=False,
            await_chain="<无可用任务句柄>",
            block_point=default_block_point,
        )

    frames = extract_task_await_frames(task)
    await_chain = format_task_await_chain(task)
    if not frames:
        return LLMBlockDiagnosis(
            state="UNKNOWN",
            status_title="⚠️ Provider 请求仍在运行 (未知阻塞点)",
            guidance_hint=f"请求正在执行中（已耗时 {elapsed_seconds:.0f}s），详细协程 await 栈见下方栈观测日志。",
            is_known=False,
            await_chain=await_chain,
            block_point=default_block_point,
        )

    # 1. 检查是否在全局限流排队中 (RateLimiter / Semaphore acquire)
    is_rate_limiting = any(
        (
            f.func_name in ("acquire", "_acquire", "_acquire_slot")
            or "semaphore" in f.filename.lower()
            or "globalratelimiter" in f.filename.lower()
        )
        and (
            "semaphore" in f.filename.lower()
            or "globalratelimiter" in f.filename.lower()
            or "locks" in f.filename.lower()
            or "resilience" in f.filename.lower()
        )
        for f in frames
    )
    if is_rate_limiting:
        return LLMBlockDiagnosis(
            state="RATE_LIMIT_QUEUE",
            status_title="⏳ 正在排队等待全局大模型并发槽位 (并发排队中)",
            guidance_hint=(
                f"当前并发大模型任务已达上限，正在排队等待释放槽位（已排队 {elapsed_seconds:.0f}s）。"
                "如需提升并发，可在插件配置中适当调整 llm_max_concurrent。"
            ),
            is_known=True,
            await_chain=await_chain,
            block_point="limiter.queue",
        )

    # 2. 检查是否为 SDK 故障退避重试 (request_retry / AsyncRetrying 在重试等待中)
    retry_frame_idx = next(
        (
            idx
            for idx, f in enumerate(frames)
            if "request_retry" in f.filename.lower()
            or "retry" in f.func_name.lower()
            or "tenacity" in f.filename.lower()
        ),
        None,
    )
    if retry_frame_idx is not None:
        sub_frames = frames[retry_frame_idx + 1 :]
        is_querying = any(
            any(
                q in f.func_name.lower()
                for q in (
                    "query",
                    "text_chat",
                    "create",
                    "send",
                    "handle_async_request",
                )
            )
            or any(
                k in f.filename.lower()
                for k in (
                    "openai",
                    "anthropic",
                    "google",
                    "httpcore",
                    "httpx",
                    "aiohttp",
                )
            )
            for f in sub_frames
        )
        if not is_querying:
            return LLMBlockDiagnosis(
                state="SDK_RETRY_BACKOFF",
                status_title="🔄 上游请求正在执行自动重试等待 (SDK 故障退避中)",
                guidance_hint=(
                    f"上游 API 请求失败，AstrBot 正在进行退避重试（耗时已达 {elapsed_seconds:.0f}s，"
                    "前序调用可能遇到了 429 频控或 5xx 临时错误）。"
                ),
                is_known=True,
                await_chain=await_chain,
                block_point="provider.retry_backoff",
            )

    # 3. 检查是否为网络建连 / TCP / SSL 握手阻塞
    is_connecting = any(
        any(
            conn_kw in f.func_name.lower()
            for conn_kw in (
                "do_handshake",
                "getaddrinfo",
                "open_connection",
                "create_connection",
                "connect_tcp",
                "connect",
            )
        )
        or any(k in f.filename.lower() for k in ("ssl", "connector", "connect"))
        for f in frames
    )
    has_entered_reading = any(
        any(
            r in f.func_name.lower()
            for r in (
                "aread",
                "read",
                "receive_response",
                "read_stream",
            )
        )
        for f in frames
    )

    if is_connecting and not has_entered_reading:
        return LLMBlockDiagnosis(
            state="CONNECTING_NETWORK",
            status_title="🌐 正在尝试与大模型 API 服务端建立网络连接 (TCP/SSL 握手中)",
            guidance_hint=(
                f"网络连接或 SSL 握手耗时已达 {elapsed_seconds:.0f}s。"
                "请检查网络代理连通性、API 中转站域名或网络出口状态。"
            ),
            is_known=True,
            await_chain=await_chain,
            block_point="network.connect",
        )

    # 4. 检查是否正在等待大模型服务端生成返回数据 (LLM 推理中 / 接收响应流)
    is_generating = any(
        any(
            gen_kw in f.func_name.lower()
            for gen_kw in (
                "aread",
                "read",
                "receive_response",
                "read_stream",
                "async_generator_asend",
                "text_chat",
                "query",
                "llm_generate",
                "completions",
            )
        )
        or any(
            k in f.filename.lower()
            for k in (
                "openai",
                "anthropic",
                "google",
                "httpx",
                "httpcore",
                "aiohttp",
                "context.py",
            )
        )
        for f in frames
    )

    if is_generating:
        return LLMBlockDiagnosis(
            state="WAITING_UPSTREAM_RESPONSE",
            status_title="⌛ 正在等待大模型服务端生成返回数据 (LLM 推理中)",
            guidance_hint=(
                f"网络连接已正常建立，当前正在等待大模型服务端推理生成（耗时已达 {elapsed_seconds:.0f}s，"
                "长文本或深度思考模型生成较慢，请耐心等待）。"
            ),
            is_known=True,
            await_chain=await_chain,
            block_point=default_block_point,
        )

    # 5. 未知阻塞点（Fallback：不符合已知 LLM/HTTP 链路的普通协程）
    return LLMBlockDiagnosis(
        state="UNKNOWN",
        status_title="⚠️ Provider 请求仍在运行 (未知阻塞点)",
        guidance_hint=f"请求正在执行中（已耗时 {elapsed_seconds:.0f}s），详细协程 await 栈见下方栈观测日志。",
        is_known=False,
        await_chain=await_chain,
        block_point=default_block_point,
    )
