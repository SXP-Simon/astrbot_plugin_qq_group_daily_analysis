"""
PDF工具模块
负责PDF相关的安装和管理功能
"""

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor

from astrbot.api import logger


class PDFInstaller:
    """PDF功能安装器"""

    # 类级别的线程池，用于异步下载任务
    _executor = ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="chromium_download"
    )
    _download_status = {
        "in_progress": False,
        "completed": False,
        "failed": False,
        "error_message": None,
    }

    @staticmethod
    async def install_pyppeteer(config_manager):
        """安装pyppeteer依赖"""
        try:
            logger.info("开始安装 pyppeteer...")

            # 使用asyncio安装pyppeteer和兼容的websockets版本
            logger.info("安装 pyppeteer==1.0.2 和兼容的依赖...")
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "pip",
                "install",
                "pyppeteer==1.0.2",
                "websockets==10.4",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info("pyppeteer 安装成功")
                logger.info(f"安装输出: {stdout.decode()}")

                # 重新加载pyppeteer模块
                success = config_manager.reload_pyppeteer()
                if success:
                    return "✅ pyppeteer 安装成功！PDF 功能现已可用。"
                else:
                    return "⚠️ pyppeteer 安装完成，但重新加载失败。请重启 AstrBot 以使用 PDF 功能。"
            else:
                error_msg = stderr.decode()
                logger.error(f"pyppeteer 安装失败: {error_msg}")
                return f"❌ pyppeteer 安装失败: {error_msg}"

        except Exception as e:
            logger.error(f"安装 pyppeteer 时出错: {e}")
            return f"❌ 安装过程中出错: {str(e)}"

    @staticmethod
    async def install_system_deps():
        """安装系统依赖（Linux下安装库，所有平台下载Chromium）"""
        try:
            logger.info("开始安装 PDF 功能系统依赖...")

            # 1. 如果是Linux，尝试安装系统库
            if sys.platform.startswith("linux"):
                linux_deps_result = await PDFInstaller._install_linux_deps()
                if linux_deps_result:
                    logger.info(f"Linux 依赖安装结果: {linux_deps_result}")

            # 2. 也是原有的逻辑：自动下载 Chromium
            logger.info("正在通过 pyppeteer 自动安装 Chromium...")

            # 检查是否已经在下载中
            if PDFInstaller._download_status["in_progress"]:
                return "⏳ Chromium 正在后台下载中，请稍候..."

            # 启动异步下载任务
            PDFInstaller._download_status["in_progress"] = True
            PDFInstaller._download_status["completed"] = False
            PDFInstaller._download_status["failed"] = False
            PDFInstaller._download_status["error_message"] = None

            # 在后台线程中启动下载
            asyncio.create_task(PDFInstaller._background_chromium_download())

            return """🚀 依赖安装任务已启动

1. Linux 系统依赖正在尝试自动安装...
2. Chromium 下载已在后台启动...

这可能需要几分钟时间，请稍候...
下载过程不会阻塞 Bot 的正常运行。

如果下载超时（10分钟），将自动取消。"""

        except Exception as e:
            PDFInstaller._download_status["in_progress"] = False
            PDFInstaller._download_status["failed"] = True
            PDFInstaller._download_status["error_message"] = str(e)
            logger.error(f"启动依赖安装时出错: {e}")
            return f"❌ 启动依赖安装时出错: {str(e)}"

    @staticmethod
    async def _install_linux_deps():
        """尝试在 Linux 下安装 Chromium 所需的依赖库"""
        try:
            # 检查是否是 Debian/Ubuntu 系列
            try:
                # 简单检查 apt-get 是否存在
                process = await asyncio.create_subprocess_exec(
                    "which",
                    "apt-get",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await process.communicate()
                if process.returncode != 0:
                    return "非 Debian/Ubuntu 系统，跳过自动安装系统库"
            except Exception:
                return "无法检测包管理器，跳过自动安装系统库"

            logger.info("检测到 Debian/Ubuntu 系统，开始安装依赖库...")

            # 依赖列表
            deps = [
                "ca-certificates",
                "fonts-liberation",
                "libappindicator3-1",
                "libasound2",
                "libatk-bridge2.0-0",
                "libatk1.0-0",
                "libc6",
                "libcairo2",
                "libcups2",
                "libdbus-1-3",
                "libexpat1",
                "libfontconfig1",
                "libgbm1",
                "libgcc1",
                "libglib2.0-0",
                "libgtk-3-0",
                "libnspr4",
                "libnss3",
                "libpango-1.0-0",
                "libpangocairo-1.0-0",
                "libstdc++6",
                "libx11-6",
                "libx11-xcb1",
                "libxcb1",
                "libxcomposite1",
                "libxcursor1",
                "libxdamage1",
                "libxext6",
                "libxfixes3",
                "libxi6",
                "libxrandr2",
                "libxrender1",
                "libxss1",
                "libxtst6",
                "lsb-release",
                "wget",
                "xdg-utils",
                # Chinese Fonts
                "fonts-noto-cjk",
                "fonts-wqy-zenhei",
                # Emoji Fonts
                "fonts-noto-color-emoji",
            ]

            # 使用 shell=True 来执行连接命令，但在 asyncio 中通常使用 shell wrap
            # 这里我们分两步执行

            logger.info("执行: apt-get update")
            proc_update = await asyncio.create_subprocess_shell(
                "apt-get update",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc_update.communicate()
            if proc_update.returncode != 0:
                logger.error(f"apt-get update 失败: {stderr.decode()}")
                return f"apt-get update 失败: {stderr.decode()[:100]}..."

            logger.info("执行: apt-get install ...")
            install_cmd = "apt-get install -y --no-install-recommends " + " ".join(deps)
            proc_install = await asyncio.create_subprocess_shell(
                install_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc_install.communicate()

            if proc_install.returncode == 0:
                logger.info("Linux 系统依赖库安装成功")
                return "✅ Linux 系统依赖库安装成功"
            else:
                start_err = stderr.decode()[:200]
                logger.error(f"Linux 系统依赖库安装失败: {stderr.decode()}")
                return f"❌ Linux 系统依赖库安装失败: {start_err}..."

        except Exception as e:
            logger.error(f"Linux 依赖安装异常: {e}")
            return f"❌ Linux 依赖安装异常: {e}"

    @staticmethod
    async def _background_chromium_download():
        """后台下载 Chromium，带超时控制"""
        try:
            logger.info("后台 Chromium 下载任务开始")

            # 设置10分钟超时
            timeout_seconds = 600

            try:
                # 使用 asyncio.wait_for 实现超时控制
                success = await asyncio.wait_for(
                    PDFInstaller._download_chromium_via_pyppeteer(),
                    timeout=timeout_seconds,
                )

                if success:
                    PDFInstaller._download_status["completed"] = True
                    PDFInstaller._download_status["failed"] = False
                    logger.info("✅ Chromium 后台下载完成！")
                    return "✅ Chromium 后台下载完成！"
                else:
                    PDFInstaller._download_status["failed"] = True
                    PDFInstaller._download_status["error_message"] = (
                        "下载失败，请检查网络连接"
                    )
                    logger.error("❌ Chromium 下载失败")
                    return "❌ Chromium 下载失败"

            except asyncio.TimeoutError:
                PDFInstaller._download_status["failed"] = True
                PDFInstaller._download_status["error_message"] = (
                    f"下载超时（{timeout_seconds}秒）"
                )
                logger.error(f"❌ Chromium 下载超时（{timeout_seconds}秒）")
                return f"❌ Chromium 下载超时（{timeout_seconds}秒）"

        except Exception as e:
            PDFInstaller._download_status["failed"] = True
            PDFInstaller._download_status["error_message"] = str(e)
            logger.error(f"后台下载 Chromium 时出错: {e}", exc_info=True)
            return f"❌ 后台下载 Chromium 时出错: {e}"
        finally:
            PDFInstaller._download_status["in_progress"] = False

    @staticmethod
    async def _download_chromium_via_pyppeteer():
        """通过 pyppeteer 自动下载 Chromium（不启动浏览器）"""
        try:
            logger.info("开始通过 pyppeteer 下载 Chromium...")

            # 尝试方法1：使用 pyppeteer-install 命令行工具
            # 这是官方推荐的安装方式，会自动处理版本和路径
            try:
                logger.info("方法1: 尝试调用 pyppeteer-install 命令...")
                process = await asyncio.create_subprocess_exec(
                    "pyppeteer-install",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    logger.info(f"✅ pyppeteer-install 执行成功: {stdout.decode()}")
                    return True
                else:
                    logger.warning(f"pyppeteer-install 执行失败: {stderr.decode()}")
            except Exception as e:
                logger.warning(f"无法调用 pyppeteer-install 命令: {e}")

            # 尝试方法2：直接调用内部下载函数
            try:
                logger.info("方法2: 尝试直接调用 pyppeteer.chromium_downloader...")
                import pyppeteer.chromium_downloader

                # 检查是否已存在
                if pyppeteer.chromium_downloader.check_chromium():
                    logger.info("✅ Chromium 已存在，无需下载")
                    return True

                logger.info("正在下载 Chromium...")
                # download_chromium 是同步阻塞的，需要在线程池中运行
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, pyppeteer.chromium_downloader.download_chromium
                )

                if pyppeteer.chromium_downloader.check_chromium():
                    logger.info("✅ Chromium 下载验证成功")
                    return True
                else:
                    logger.error("❌ Chromium 下载函数执行完成但未发现可执行文件")
                    return False

            except Exception as e:
                logger.error(f"直接调用下载函数失败: {e}")

            return False

        except Exception as e:
            logger.error(f"下载过程发生未知错误: {e}")
            return False

    @staticmethod
    def get_pdf_status(config_manager) -> str:
        """获取PDF功能状态"""
        if config_manager.pyppeteer_available:
            version = config_manager.pyppeteer_version or "未知版本"
            return f"✅ PDF 功能可用 (pyppeteer {version})"
        else:
            return "❌ PDF 功能不可用 - 需要安装 pyppeteer"
