"""
OneBot 协议端驱动工厂 (OneBot Driver Factory)

根据 get_version_info 响应中的 app_name 或配置自动匹配并创建对应的 OneBotDriver 实例。
"""

from typing import Any

from .....utils.logger import logger
from .driver_base import OneBotDriver
from .llbot_driver import LLOneBotDriver
from .napcat_driver import NapCatDriver
from .snowluma_driver import SnowLumaDriver
from .standard_driver import StandardOneBotDriver


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
        """通过向 bot 发起 get_version_info 探测并创建驱动。"""
        if not hasattr(bot, "call_action"):
            logger.debug("[OneBot] bot 实例无 call_action 接口，使用标准驱动")
            return StandardOneBotDriver()

        try:
            result = await bot.call_action("get_version_info")
            if isinstance(result, dict):
                app_name = result.get("app_name") or result.get("name")
                if not app_name:
                    logger.debug(
                        f"[OneBot] get_version_info 响应中无 app_name 字段: {result}，绑定标准驱动"
                    )
                return cls.create_driver_by_app_name(app_name)
            logger.debug(
                f"[OneBot] get_version_info 响应非字典结构 ({type(result)})，绑定标准驱动"
            )
        except Exception as exc:
            logger.debug(f"[OneBot] 探测协议端版本失败，回退使用标准驱动: {exc}")

        return StandardOneBotDriver()
