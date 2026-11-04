"""使用受管理的独立编译进程生成 QQ Markdown 概览图。"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict

from .render_trace import render_span
from .typst_process import run_typst_worker


class SummaryMetric(TypedDict):
    """概览图中的格式化统计指标。"""

    value: str
    label: str


class SummaryBar(TypedDict):
    """概览图中的每小时计数与柱高。"""

    hour: str
    count: int
    height: int


async def render_native_summary(
    data_dir: Path,
    date: str,
    metrics: list[SummaryMetric],
    chart: list[SummaryBar],
    timeout_seconds: float,
) -> bytes:
    """生成透明背景概览图，供 QQ 图片链路上传。

    Args:
        data_dir: 插件数据目录，包含已下载的受管理字体。
        date: 以 JSON 文本传入的展示日期。
        metrics: 五项格式化统计指标。
        chart: 二十四小时的直方图数据。
        timeout_seconds: 独立编译允许的最长秒数。

    Returns:
        PNG 图片字节，保留至 QQ 图片发送结束。

    Raises:
        RuntimeError: 模板或受管理字体无法编译。
        TimeoutError: 编译超过配置的时限。
    """
    jobs = data_dir / "typst" / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    async with render_span(
        "RENDER_REPORT", {"kind": "qq_summary", "render_service": "typst"}
    ):
        with TemporaryDirectory(prefix="qq-summary-", dir=jobs) as directory:
            job = Path(directory)
            async with render_span("TYPST_PREPARE"):
                shutil.copyfile(
                    Path(__file__).parent
                    / "platform_templates"
                    / "qq_official"
                    / "summary_dashboard.typ",
                    job / "main.typ",
                )
                (job / "data.json").write_text(
                    json.dumps(
                        {"date": date, "metrics": metrics, "chart": chart},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            async with render_span("TYPST_COMPILE") as span:
                telemetry = await run_typst_worker(
                    job, data_dir / "typst" / "fonts", timeout_seconds
                )
                if span and telemetry:
                    span["payload"].update(telemetry)
            return await asyncio.to_thread((job / "report.png").read_bytes)
