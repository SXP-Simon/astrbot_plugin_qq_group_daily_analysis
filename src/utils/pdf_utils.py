"""
PDF工具模块
负责PDF相关的安装和管理功能
"""

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .logger import logger


class PDFInstaller:
    """
    工具组件：PDF 渲染引擎 (Playwright) 安装器

    该组件负责管理 Playwright 及其对应浏览器内核 (Chromium) 的安装生命周期。
    由于内核下载耗时较长且受网络波动影响，采用非阻塞的后台任务模式执行。
    """

    # 类级别的线程池，专用于隔离耗时的 IO/Shell 操作
    _executor = ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="playwright_install"
    )

    # 静态安装状态追踪
    _install_status: dict[str, Any] = {
        "in_progress": False,
        "completed": False,
        "failed": False,
        "error_message": None,
    }

    @staticmethod
    async def install_playwright(config_manager: Any) -> str:
        """
        异步入口：安装 Playwright 环境。

        流程：
        1. 调用 pip 安装 `playwright` Python 包。
        2. 验证自定义浏览器路径配置。
        3. 若无自定义路径，则触发浏览器内核安装。

        Args:
            config_manager (Any): 配置管理实例，用于读取/设置安装状态。

        Returns:
            str: 安装阶段提示信息
        """
        try:
            logger.info("正在初始化 Playwright 安装流程...")

            # 1. 下载并安装库文件
            logger.info("第一步：正在运行 pip install playwright...")
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "pip",
                "install",
                "playwright>=1.40.0",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(f"Playwright 库安装失败: {error_msg}")
                return f"❌ pip install playwright 失败: {error_msg}"

            logger.info("第一步完成。正在检查浏览器内核...")

            custom_path = config_manager.get_browser_path()
            if custom_path and Path(custom_path).exists():
                logger.info(f"检测到自定义浏览器路径: {custom_path}。跳过内核下载。")
                return f"✅ Playwright 库已就绪。已检测到自定义浏览器 `{custom_path}`，无需额外安装内核。您可以直接开始生成 PDF。"

            # 3. 部署浏览器内核
            return await PDFInstaller.install_system_deps()

        except Exception as e:
            logger.error(f"Playwright 设置过程中出错: {e}")
            return f"❌ 安装过程中出错: {str(e)}"

    @staticmethod
    async def install_system_deps() -> str:
        """
        触发浏览器内核的后台异步安装流程。

        该方法检查防重入状态，并立即返回任务启动信息，不会阻塞主线程。

        Returns:
            str: 任务排队状态提示
        """
        try:
            if PDFInstaller._install_status["in_progress"]:
                return "⏳ 浏览器内核正在后台部署中，请稍后检查日志或状态。"

            PDFInstaller._install_status.update(
                {
                    "in_progress": True,
                    "completed": False,
                    "failed": False,
                    "error_message": None,
                }
            )

            logger.info("正在启动后台线程以部署 Chromium 内核...")
            asyncio.create_task(PDFInstaller._background_playwright_install())

            return (
                "🚀 浏览器内核安装任务已成功在后台启动。\n\n"
                "程序正在执行 `playwright install chromium`，由于体积较大，通常需花费 2-5 分钟。\n"
                "此过程不会影响机器人正常响应。安装完成后，系统日志将进行通知。"
            )

        except Exception as e:
            PDFInstaller._install_status["in_progress"] = False
            logger.error(f"启动安装任务失败: {e}")
            return f"❌ 启动安装任务失败: {e}"

    @staticmethod
    async def _background_playwright_install() -> None:
        """
        底层宿主任务：驱动 system shell 执行浏览器二进制文件部署。
        """
        try:
            logger.info("正在执行二进制文件：playwright install chromium")

            # 通过当前 Python 解释器环境调用子模块，确保环境隔离
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "playwright",
                "install",
                "chromium",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                PDFInstaller._install_status["completed"] = True
                logger.info("✅ Chromium 内核安装成功。")

                # Linux 特殊处理：提示用户补充系统依赖
                if sys.platform.startswith("linux"):
                    logger.info(
                        "提示：在 Linux 上，如果 PDF 生成仍然失败，请尝试运行 'sudo playwright install-deps'。"
                    )
            else:
                PDFInstaller._install_status["failed"] = True
                PDFInstaller._install_status["error_message"] = stderr.decode().strip()
                logger.error(f"❌ Chromium 安装二进制文件执行失败: {stderr.decode()}")

        except Exception as e:
            PDFInstaller._install_status.update(
                {"failed": True, "error_message": str(e)}
            )
            logger.error(f"Playwright 后台任务遇到异常: {e}")
        finally:
            PDFInstaller._install_status["in_progress"] = False

    @staticmethod
    def get_pdf_status(config_manager: Any) -> str:
        """
        查询当前系统的 PDF 功能可用性状态描述。

        Args:
            config_manager (Any): 配置管理器，用于读取核心探测开关。

        Returns:
            str: 用户友好的状态文本
        """
        if config_manager.playwright_available:
            version = config_manager.playwright_version or "Unknown"
            status = f"✅ PDF 功能可用 (核心版本: {version})"

            if PDFInstaller._install_status["in_progress"]:
                status += "\n⏳ 警告：浏览器内核仍在后台下载/部署中..."
            elif PDFInstaller._install_status["failed"]:
                status += f"\n⚠️ 上次内核安装异常: {PDFInstaller._install_status.get('error_message')}"

            return status
        else:
            return "❌ PDF 渲染核心未安装 - 请发送管理员指令 `/安装PDF`。"
