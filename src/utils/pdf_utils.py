"""
PDF工具模块
负责PDF相关的安装和管理功能
"""

import sys
import asyncio
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
        """通过 pyppeteer 自动安装 Chromium（异步非阻塞方式）"""
        try:
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

            return """⏳ Chromium 下载已在后台启动

这可能需要几分钟时间，请稍候...
下载过程不会阻塞 Bot 的正常运行。

如果下载超时（10分钟），将自动取消。"""

        except Exception as e:
            PDFInstaller._download_status["in_progress"] = False
            PDFInstaller._download_status["failed"] = True
            PDFInstaller._download_status["error_message"] = str(e)
            logger.error(f"启动 Chromium 下载时出错: {e}")
            return f"❌ 启动 Chromium 下载时出错: {str(e)}"

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
                else:
                    PDFInstaller._download_status["failed"] = True
                    PDFInstaller._download_status["error_message"] = (
                        "下载失败，请检查网络连接"
                    )
                    logger.error("❌ Chromium 下载失败")

            except asyncio.TimeoutError:
                PDFInstaller._download_status["failed"] = True
                PDFInstaller._download_status["error_message"] = (
                    f"下载超时（{timeout_seconds}秒）"
                )
                logger.error(f"❌ Chromium 下载超时（{timeout_seconds}秒）")

        except Exception as e:
            PDFInstaller._download_status["failed"] = True
            PDFInstaller._download_status["error_message"] = str(e)
            logger.error(f"后台下载 Chromium 时出错: {e}", exc_info=True)
        finally:
            PDFInstaller._download_status["in_progress"] = False

    @staticmethod
    async def _download_chromium_via_pyppeteer():
        """通过 pyppeteer 自动下载 Chromium（带重试机制）"""
        max_retries = 2
        retry_count = 0

        while retry_count <= max_retries:
            try:
                if retry_count > 0:
                    logger.info(
                        f"正在重试下载 Chromium（第 {retry_count}/{max_retries} 次）..."
                    )
                else:
                    logger.info("通过 pyppeteer 自动下载 Chromium...")

                # 导入 pyppeteer 并尝试下载
                try:
                    import pyppeteer
                    from pyppeteer import launch
                    from pyppeteer.errors import BrowserError

                    # 方法1: 尝试直接下载 Chromium 而不启动浏览器
                    logger.info("尝试直接下载 Chromium...")
                    try:
                        from pyppeteer.launcher import Launcher

                        # 创建 Launcher 实例但不启动浏览器
                        launcher = Launcher(
                            headless=True,
                            args=["--no-sandbox", "--disable-setuid-sandbox"],
                        )

                        # 只下载 Chromium
                        launcher._get_chromium_revision()
                        await launcher._download_chromium()

                        logger.info("✅ Chromium 下载完成")
                        return True

                    except Exception as download_error:
                        logger.warning(f"直接下载 Chromium 失败: {download_error}")
                        logger.info("尝试通过启动浏览器来下载...")

                    # 方法2: 通过启动浏览器触发自动下载
                    import platform

                    system = platform.system().lower()

                    if system == "linux":
                        browser_args = [
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-accelerated-2d-canvas",
                            "--no-first-run",
                            "--no-zygote",
                            "--disable-gpu",
                            "--disable-background-timer-throttling",
                            "--disable-backgrounding-occluded-windows",
                            "--disable-renderer-backgrounding",
                            "--disable-features=TranslateUI",
                            "--disable-ipc-flooding-protection",
                        ]
                    else:
                        browser_args = [
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-gpu",
                        ]

                    logger.info("启动 pyppeteer 浏览器以触发 Chromium 自动下载...")
                    browser = await launch(
                        headless=True,
                        args=browser_args,
                        ignoreHTTPSErrors=True,
                        dumpio=False,  # 关闭浏览器日志输出以减少干扰
                    )

                    # 获取 Chromium 路径
                    chromium_path = pyppeteer.executablePath()
                    logger.info(f"✅ Chromium 自动下载完成，路径: {chromium_path}")

                    await browser.close()
                    return True

                except BrowserError as e:
                    logger.error(f"浏览器错误: {e}")

                    # 方法3: 使用子进程命令行触发下载
                    try:
                        logger.info("尝试使用命令行触发 Chromium 自动下载...")

                        import platform

                        system = platform.system().lower()

                        if system == "linux":
                            cmd = [
                                sys.executable,
                                "-c",
                                """
import pyppeteer
import asyncio

async def download_chrome():
    try:
        browser = await pyppeteer.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--single-process'
            ]
        )
        await browser.close()
        print("Chromium 下载成功")
    except Exception as e:
        print(f"下载失败: {e}")
        raise

asyncio.run(download_chrome())
                                """,
                            ]
                        else:
                            cmd = [
                                sys.executable,
                                "-c",
                                "import pyppeteer; import asyncio; asyncio.run(pyppeteer.launch())",
                            ]

                        process = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )

                        stdout, stderr = await process.communicate()

                        if process.returncode == 0:
                            logger.info("✅ 成功通过命令行触发 Chromium 自动下载")
                            return True
                        else:
                            logger.error(f"命令行触发自动下载失败: {stderr.decode()}")
                            raise Exception(f"命令行下载失败: {stderr.decode()}")

                    except Exception as e2:
                        logger.error(f"命令行触发自动下载失败: {e2}")
                        raise

            except Exception as e:
                retry_count += 1
                if retry_count <= max_retries:
                    wait_time = retry_count * 5  # 递增等待时间：5秒、10秒
                    logger.warning(f"下载失败，{wait_time}秒后重试... 错误: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"通过 pyppeteer 自动下载 Chromium 失败（已重试{max_retries}次）: {e}",
                        exc_info=True,
                    )
                    return False

        return False

    @staticmethod
    def get_pdf_status(config_manager) -> str:
        """获取PDF功能状态"""
        if config_manager.pyppeteer_available:
            version = config_manager.pyppeteer_version or "未知版本"
            return f"✅ PDF 功能可用 (pyppeteer {version})"
        else:
            return "❌ PDF 功能不可用 - 需要安装 pyppeteer"
