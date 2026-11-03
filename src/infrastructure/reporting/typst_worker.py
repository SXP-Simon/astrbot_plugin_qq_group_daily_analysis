"""独立 Typst 编译进程；不导入 AstrBot，不执行报告正文中的代码。"""

from __future__ import annotations

import json
import math
import sys
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

REPORT_WIDTH = 940
REPORT_PPI = 144
CUSTOM_TEMPLATE_MARKER = ".typst-custom"


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


def compile_report(job_dir: Path, font_dir: Path) -> None:
    """先测量像素预算，再直接编译 PNG。

    Args:
        job_dir: 只含模板、JSON 和已校验图片的任务根目录。
        font_dir: 插件 data 目录内的受管理字体目录。

    Raises:
        RuntimeError: 缺少中文字体、依赖或报告超过像素预算。
    """
    try:
        import typst
    except ImportError as exc:
        raise RuntimeError("请安装插件 requirements.txt 中的 typst 依赖") from exc
    fonts = typst.Fonts(include_system_fonts=False, font_paths=[str(font_dir)])
    families = fonts.families()
    if not any("Noto Sans CJK" in name or "Noto Sans SC" in name for name in families):
        raise RuntimeError("Typst 缺少中文字体，请在 WebUI 下载预设字体到插件数据目录")
    compiler = typst.Compiler(
        str(job_dir / "main.typ"),
        root=str(job_dir),
        font_paths=fonts,
        ignore_system_fonts=True,
    )
    try:
        if (job_dir / CUSTOM_TEMPLATE_MARKER).is_file():
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
    except typst.TypstError as error:
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
    compiler.compile(output=str(job_dir / "report.png"), format="png", ppi=REPORT_PPI)
    if (job_dir / "report.png").stat().st_size > 32 * 1024 * 1024:
        raise RuntimeError("Typst 报告超过 32 MiB，无法发送")


if __name__ == "__main__":
    try:
        compile_report(Path(sys.argv[1]), Path(sys.argv[2]))
    except Exception as error:
        sys.stderr.buffer.write(f"Typst 编译失败：{error}\n".encode())
        sys.exit(1)
