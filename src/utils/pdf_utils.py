"""
PDF工具模块
负责PDF相关的安装和管理功能
"""

import sys
import asyncio
from astrbot.api import logger


class PDFInstaller:
    """PDF功能安装器"""

    @staticmethod
    async def install_pyppeteer(config_manager):
        """安装pyppeteer依赖"""
        try:
            logger.info("开始安装 pyppeteer...")

            # 使用asyncio安装pyppeteer和兼容的websockets版本
            logger.info("安装 pyppeteer==1.0.2 和兼容的依赖...")
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install",
                "pyppeteer==1.0.2", "websockets==10.4",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
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
        """通过 pyppeteer 自动安装 Chromium"""
        try:
            logger.info("正在通过 pyppeteer 自动安装 Chromium...")
            
            # 直接通过 pyppeteer 下载 Chromium
            success = await PDFInstaller._download_chromium_via_pyppeteer()
            
            if success:
                return """✅ Chromium 自动安装成功！

系统依赖已自动配置完成。
现在可以使用 PDF 功能了。"""
            else:
                return """⚠️ 通过 pyppeteer 自动安装 Chromium 失败

请尝试以下方法：
1. 确保网络连接正常
2. 检查是否有防火墙或代理限制
3. 手动运行：path/to/your/actual/sys/executable/python -c "import pyppeteer; import asyncio; asyncio.run(pyppeteer.launch())"
4. 或者手动安装 Chrome/Chromium 浏览器

安装完成后，重启 AstrBot"""

        except Exception as e:
            logger.error(f"通过 pyppeteer 安装 Chromium 时出错: {e}")
            return f"❌ 通过 pyppeteer 安装 Chromium 时出错: {str(e)}"

    @staticmethod
    async def _download_chromium_via_pyppeteer():
        """通过 pyppeteer 自动下载 Chromium"""
        try:
            logger.info("通过 pyppeteer 自动下载 Chromium...")
            
            # 导入 pyppeteer 并尝试下载
            try:
                import pyppeteer
                from pyppeteer import launch
                
                # 尝试启动浏览器，这会触发自动下载
                logger.info("启动 pyppeteer 浏览器以触发 Chromium 自动下载...")
                
                # 根据操作系统设置不同的参数
                import platform
                system = platform.system().lower()
                
                if system == "linux":
                    # Linux 环境下需要更多参数来避免权限问题
                    browser_args = [
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--no-first-run',
                        '--no-zygote',
                        '--single-process',
                        '--disable-gpu'
                    ]
                else:
                    # Windows/macOS 环境下的标准参数
                    browser_args = [
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-gpu'
                    ]
                
                browser = await launch(
                    headless=True,
                    args=browser_args
                )
                
                # 获取 Chromium 路径
                chromium_path = pyppeteer.executablePath()
                logger.info(f"Chromium 自动下载完成，路径: {chromium_path}")
                
                await browser.close()
                return True
                
            except Exception as e:
                logger.error(f"通过 pyppeteer 自动下载 Chromium 失败: {e}", exc_info=True)
                
                # 备用方法：使用命令行触发下载
                try:
                    logger.info("尝试使用命令行触发 Chromium 自动下载...")
                    process = await asyncio.create_subprocess_exec(
                        sys.executable, "-c",
                        "import pyppeteer; import asyncio; asyncio.run(pyppeteer.launch())",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        logger.info("成功通过命令行触发 Chromium 自动下载")
                        return True
                    else:
                        logger.error(f"命令行触发自动下载失败: {stderr.decode()}")
                        return False
                        
                except Exception as e2:
                    logger.error(f"命令行触发自动下载也失败: {e2}")
                    return False
                    
        except Exception as e:
            logger.error(f"通过 pyppeteer 自动下载 Chromium 时出错: {e}", exc_info=True)
            return False

    @staticmethod
    def get_pdf_status(config_manager) -> str:
        """获取PDF功能状态"""
        if config_manager.pyppeteer_available:
            version = config_manager.pyppeteer_version or "未知版本"
            return f"✅ PDF 功能可用 (pyppeteer {version})"
        else:
            return "❌ PDF 功能不可用 - 需要安装 pyppeteer"