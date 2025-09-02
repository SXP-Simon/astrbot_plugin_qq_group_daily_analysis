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
    def get_pdf_status(config_manager) -> str:
        """获取PDF功能状态"""
        if config_manager.pyppeteer_available:
            version = config_manager.pyppeteer_version or "未知版本"
            return f"✅ PDF 功能可用 (pyppeteer {version})"
        else:
            return "❌ PDF 功能不可用 - 需要安装 pyppeteer"