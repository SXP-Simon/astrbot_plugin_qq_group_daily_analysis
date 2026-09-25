"""
OneBot 协议端驱动工厂 (OneBot Driver Factory)

根据 get_version_info 响应中的 app_name 或配置自动匹配并创建对应的 OneBotDriver 实例。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .....utils.logger import logger
from .llbot_driver import LLOneBotDriver
from .napcat_driver import NapCatDriver
from .snowluma_driver import SnowLumaDriver
from .standard_driver import StandardOneBotDriver

if TYPE_CHECKING:
    from .driver_base import OneBotDriver


class OneBotDriverFactory:
    """OneBot 驱动探测与创建工厂。"""

    @classmethod
    def create_driver_by_app_name(cls, app_name: str | None) -> OneBotDriver:
        """根据 app_name 字符串实例化对应的驱动。"""
        if not app_name:
            return StandardOneBotDriver()

        name = app_name.strip().lower()

        if "snowluma" in name:
            logger.info("[OneBot] 探测并绑定协议端驱动: SnowLuma")
            return SnowLumaDriver()

        if "llonebot" in name or "llbot" in name or "luckylilliabot" in name:
            logger.info("[OneBot] 探测并绑定协议端驱动: LLOneBot")
            return LLOneBotDriver()

        if "napcat" in name:
            logger.info("[OneBot] 探测并绑定协议端驱动: NapCat")
            return NapCatDriver()

        logger.info(
            f"[OneBot] 探测到协议端 app_name='{app_name}'，绑定标准驱动: StandardOneBot"
        )
        return StandardOneBotDriver()

    @classmethod
    async def detect_driver(cls, bot: Any) -> OneBotDriver:
        """通过向 bot 发起 get_version_info / get_version (OB12) 探测并创建驱动。"""
        if not hasattr(bot, "call_action"):
            logger.debug("[OneBot] bot 实例无 call_action 接口，使用标准驱动")
            return StandardOneBotDriver()

        # 1. 优先尝试 OneBot v11 标准 get_version_info
        try:
            result = await bot.call_action("get_version_info")
            if isinstance(result, dict):
                # 兼容顶层直接返回或包装在 data 字典中的响应格式
                app_name = (
                    result.get("app_name") or result.get("name") or result.get("impl")
                )
                if not app_name:
                    inner_data = result.get("data")
                    if isinstance(inner_data, dict):
                        app_name = (
                            inner_data.get("app_name")
                            or inner_data.get("name")
                            or inner_data.get("impl")
                        )
                if app_name:
                    return cls.create_driver_by_app_name(str(app_name))
                logger.debug(
                    f"[OneBot] get_version_info 响应中无 app_name/impl 字段: {result}"
                )
        except Exception as exc:
            logger.debug(
                f"[OneBot] get_version_info 调用失败: {exc}，尝试 get_version (OB12)..."
            )

        # 2. 尝试 OneBot v12 标准 get_version
        try:
            result_v12 = await bot.call_action("get_version")
            if isinstance(result_v12, dict):
                app_name = (
                    result_v12.get("impl")
                    or result_v12.get("app_name")
                    or result_v12.get("name")
                )
                if not app_name:
                    inner_data_v12 = result_v12.get("data")
                    if isinstance(inner_data_v12, dict):
                        app_name = (
                            inner_data_v12.get("impl")
                            or inner_data_v12.get("app_name")
                            or inner_data_v12.get("name")
                        )
                if app_name:
                    logger.debug(
                        f"[OneBot] 通过 OneBot v12 get_version 识别到实现: {app_name}"
                    )
                    return cls.create_driver_by_app_name(str(app_name))
        except Exception as exc_v12:
            logger.debug(f"[OneBot] get_version (OB12) 调用失败: {exc_v12}")

        logger.debug("[OneBot] 未能从协议端获取到版本名称，回退使用标准驱动")
        return StandardOneBotDriver()
