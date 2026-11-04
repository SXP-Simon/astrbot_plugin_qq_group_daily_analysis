"""独立 Typst 编译进程；不导入 AstrBot，不执行报告正文中的代码。"""

from __future__ import annotations

import json
import math
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict
from xml.etree import ElementTree

if TYPE_CHECKING:
    from typst import Compiler

REPORT_WIDTH = 940
REPORT_PPI = 144
CUSTOM_TEMPLATE_MARKER = ".typst-custom"


class TypstWorkerMetrics(TypedDict, total=False):
    """隔离进程的测量值，内存不与宿主进程 RSS 混算。"""

    font_setup_ms: float
    layout_ms: float
    raster_ms: float
    raster_cpu_ms: float
    worker_cpu_ms: float
    cpu_quota_cores: float
    raster_ppi: float
    worker_peak_rss_mb: float
    worker_start_rss_mb: float
    worker_peak_delta_mb: float
    worker_rss_source: str
    worker_phase: str
    worker_metrics_partial: bool


def _custom_page_size(svg: bytes | list[bytes] | None) -> tuple[float, float]:
    """在栅格化前读取自定义模板实际画布，不信任模板自行声明的尺寸。

    Args:
        svg: Typst 矢量导出结果；多页结果会被拒绝。

    Returns:
        实际画布的像素宽度与高度。

    Raises:
        RuntimeError: 模板分页或无法解析真实画布尺寸。
    """
    if not isinstance(svg, bytes):
        raise RuntimeError("Typst 自定义模板必须生成单张静态长图，不能分页")
    try:
        # 只读取根元素，不为整份 SVG 建立 XML 树或分配像素面。
        with BytesIO(svg) as stream:
            _, root = next(ElementTree.iterparse(stream, events=("start",)))
            _, _, width, height = (
                float(value) for value in root.attrib["viewBox"].split()
            )
        return width * REPORT_PPI / 72, height * REPORT_PPI / 72
    except (ElementTree.ParseError, KeyError, ValueError, StopIteration) as error:
        raise RuntimeError("无法读取 Typst 自定义模板的实际画布尺寸") from error


def _check_canvas(
    compiler: Compiler, *, custom: bool, raster_ppi: int = REPORT_PPI
) -> int:
    """在分配像素面之前测量真实版心并校验静态报告预算。

    Args:
        compiler: 已加载模板与字体的编译器。
        custom: 自定义模板使用实际矢量画布，不信任尺寸元数据。
        raster_ppi: 期望的导出密度。

    Returns:
        像素预算允许的最高密度；超长图逐档回落，排版保持不变。

    Raises:
        RuntimeError: 模板语法、宽度、页数或像素预算不符合要求。
    """
    from typst import TypstError

    if type(raster_ppi) is not int or raster_ppi not in (144, 180, 216):
        raise RuntimeError("Typst 导出密度只允许 144、180 或 216 PPI")
    try:
        if custom:
            pixel_width, pixel_height = _custom_page_size(
                compiler.compile(format="svg")
            )
        else:
            try:
                measured = json.loads(
                    compiler.query("<report-size>", field="value", one=True)
                )
            except RuntimeError:
                # query 的错误没有定位信息，用矢量编译取得源码位置，仍不分配像素面。
                compiler.compile(format="svg")
                raise
            pixel_width = REPORT_WIDTH
            pixel_height = float(measured["height"]) * REPORT_PPI / 72
    except TypstError as error:
        raise RuntimeError(error.diagnostic) from error
    if not all(
        math.isfinite(value) and value > 0 for value in (pixel_width, pixel_height)
    ):
        raise RuntimeError("Typst 报告画布尺寸无效")
    if abs(pixel_width - REPORT_WIDTH) > 1:
        raise RuntimeError(
            f"Typst 自定义模板须固定为 {REPORT_WIDTH}px 宽，当前为 {pixel_width:g}px"
        )
    if pixel_height > 30000 or pixel_height * pixel_width > 40_000_000:
        raise RuntimeError("Typst 报告超过单图像素预算，请减少展示条数")
    for candidate in (216, 180, 144):
        if candidate > raster_ppi:
            continue
        scale = candidate / REPORT_PPI
        width, height = math.ceil(pixel_width * scale), math.ceil(pixel_height * scale)
        if width <= 1410 and height <= 30000 and width * height <= 40_000_000:
            return candidate
    raise RuntimeError("Typst 报告超过单图像素预算，请减少展示条数")


def compile_report(
    job_dir: Path,
    font_dir: Path,
    metrics: TypstWorkerMetrics | None = None,
    raster_ppi: int = REPORT_PPI,
) -> None:
    """先测量像素预算，再直接编译 PNG。

    Args:
        job_dir: 只含模板、JSON 和已校验图片的任务根目录。
        font_dir: 插件 data 目录内的受管理字体目录。
        metrics: 遥测开启时填充阶段测量值；默认不收集。
        raster_ppi: 受限的栅格密度；字体与排版仍按 144 PPI 的逻辑尺寸处理。

    Raises:
        RuntimeError: 缺少中文字体、依赖或报告超过像素预算。
    """
    cpu_started = time.process_time()
    _collect_cpu_quota(metrics)
    _collect_peak(metrics, baseline=True)
    _publish_metrics(metrics, "font_setup")
    try:
        import typst
    except ImportError as exc:
        raise RuntimeError("请安装插件 requirements.txt 中的 typst 依赖") from exc
    try:
        phase_start = time.perf_counter()
        fonts = typst.Fonts(include_system_fonts=False, font_paths=[str(font_dir)])
        families = fonts.families()
        if not any(
            "Noto Sans CJK" in name or "Noto Sans SC" in name for name in families
        ):
            raise RuntimeError(
                "Typst 缺少中文字体，请在 WebUI 下载预设字体到插件数据目录"
            )
        compiler = typst.Compiler(
            str(job_dir / "main.typ"),
            root=str(job_dir),
            font_paths=fonts,
            ignore_system_fonts=True,
        )
        if metrics is not None:
            metrics["font_setup_ms"] = round(
                (time.perf_counter() - phase_start) * 1000, 2
            )
        phase_start = time.perf_counter()
        _publish_metrics(metrics, "layout")
        try:
            raster_ppi = _check_canvas(
                compiler,
                custom=(job_dir / CUSTOM_TEMPLATE_MARKER).is_file(),
                raster_ppi=raster_ppi,
            )
            if metrics is not None:
                metrics["raster_ppi"] = raster_ppi
        finally:
            if metrics is not None:
                metrics["layout_ms"] = round(
                    (time.perf_counter() - phase_start) * 1000, 2
                )
        phase_start = time.perf_counter()
        _publish_metrics(metrics, "raster")
        raster_cpu_started = time.process_time()
        compiler.compile(
            output=str(job_dir / "report.png"), format="png", ppi=raster_ppi
        )
        if (job_dir / "report.png").stat().st_size > 32 * 1024 * 1024:
            raise RuntimeError("Typst 报告超过 32 MiB，无法发送")
        if metrics is not None:
            metrics["raster_ms"] = round((time.perf_counter() - phase_start) * 1000, 2)
            metrics["raster_cpu_ms"] = round(
                (time.process_time() - raster_cpu_started) * 1000, 2
            )
        _publish_metrics(metrics, "complete")
    finally:
        if metrics is not None:
            metrics["worker_cpu_ms"] = round(
                (time.process_time() - cpu_started) * 1000, 2
            )
        _collect_peak(metrics)


def _collect_cpu_quota(metrics: TypstWorkerMetrics | None) -> None:
    """读取常见容器挂载根的 CPU 配额，未知时省略而不猜测无限制。

    Args:
        metrics: 已有遥测开关控制的目标，不扫描宿主或其他进程。
    """
    if metrics is None or sys.platform != "linux":
        return
    for quota_path, period_path in (
        (Path("/sys/fs/cgroup/cpu.max"), None),
        (
            Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"),
            Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us"),
        ),
        (
            Path("/sys/fs/cgroup/cpu,cpuacct/cpu.cfs_quota_us"),
            Path("/sys/fs/cgroup/cpu,cpuacct/cpu.cfs_period_us"),
        ),
    ):
        try:
            if period_path is None:
                quota, period = quota_path.read_text(encoding="ascii").split()
            else:
                quota, period = (
                    quota_path.read_text(encoding="ascii"),
                    period_path.read_text(encoding="ascii"),
                )
            if quota.strip() != "max" and int(quota) > 0 and int(period) > 0:
                metrics["cpu_quota_cores"] = int(quota) / int(period)
            return
        except (OSError, ValueError):
            continue


def _collect_peak(
    metrics: TypstWorkerMetrics | None,
    *,
    baseline: bool = False,
    pid: int | None = None,
) -> None:
    """记录隔离编译自身的 RSS 峰值，避免 Linux 启动前的继承统计污染。

    Args:
        metrics: 可选遥测目标，与宿主 RSS 分开保存。
        baseline: 在加载编译器前记录启动 RSS，供计算峰值增长量。
        pid: 超时终止前读取指定子进程；省略时采集当前工作进程。
    """
    if metrics is None:
        return
    if pid is not None and (pid <= 0 or sys.platform not in ("win32", "linux")):
        return
    try:
        if sys.platform == "win32":
            import psutil

            try:
                info = psutil.Process(pid).memory_info()
            except psutil.Error:
                return
            peak = info._asdict()["peak_wset"] / 1024**2
            if baseline:
                metrics["worker_start_rss_mb"] = round(info.rss / 1024**2, 2)
            source = "windows_working_set"
        elif sys.platform == "linux":
            # ru_maxrss 跨 exec 保留，可能带入 AstrBot 的大内存；VmHWM 属于当前映像。
            fields = dict(
                line.split(":", 1)
                for line in (
                    Path("/proc") / (str(pid) if pid is not None else "self") / "status"
                )
                .read_text(encoding="ascii")
                .splitlines()
                if line.startswith(("VmHWM:", "VmRSS:"))
            )
            peak = float(fields["VmHWM"].split()[0]) / 1024
            if baseline:
                metrics["worker_start_rss_mb"] = round(
                    float(fields["VmRSS"].split()[0]) / 1024, 2
                )
            source = "linux_proc_status"
        else:
            import resource

            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
                1024**2 if sys.platform == "darwin" else 1024
            )
            source = "posix_getrusage"
        metrics["worker_peak_rss_mb"] = round(peak, 2)
        metrics["worker_rss_source"] = source
        if "worker_start_rss_mb" in metrics:
            metrics["worker_peak_delta_mb"] = round(
                max(0.0, peak - metrics["worker_start_rss_mb"]), 2
            )
    except (ImportError, OSError, KeyError, ValueError, IndexError):
        pass


def _publish_metrics(metrics: TypstWorkerMetrics | None, phase: str) -> None:
    """在阶段切换时刷新有限遥测，进程被终止后仍可读取最后进度。

    Args:
        metrics: 仅在现有遥测开关启用时传入。
        phase: 当前字体、布局、栅格化或完成阶段。
    """
    if metrics is not None:
        metrics["worker_phase"] = phase
        _collect_peak(metrics)
        sys.stdout.write(json.dumps(metrics) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    telemetry: TypstWorkerMetrics | None = {} if "--metrics" in sys.argv[3:] else None
    try:
        ppi = (
            int(sys.argv[sys.argv.index("--ppi") + 1])
            if "--ppi" in sys.argv
            else REPORT_PPI
        )
        compile_report(Path(sys.argv[1]), Path(sys.argv[2]), telemetry, raster_ppi=ppi)
    except Exception as error:
        sys.stderr.buffer.write(f"Typst 编译失败：{error}\n".encode())
        sys.exit(1)
    finally:
        if telemetry is not None:
            sys.stdout.write(json.dumps(telemetry) + "\n")
            sys.stdout.flush()
