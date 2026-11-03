"""独立 Typst 编译进程；不导入 AstrBot，不执行报告正文中的代码。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPORT_WIDTH = 940
REPORT_PPI = 144


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
        measured = json.loads(compiler.query("<report-size>", field="value", one=True))
    except RuntimeError:
        # query 的错误没有定位信息，失败时用矢量编译取得源码位置，仍不分配栅格图。
        try:
            compiler.compile(format="svg")
        except typst.TypstError as error:
            raise RuntimeError(error.diagnostic) from error
        raise
    pixel_height = float(measured["height"]) * REPORT_PPI / 72
    if pixel_height > 30000 or pixel_height * REPORT_WIDTH > 40_000_000:
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
