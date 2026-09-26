from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ...config.config_manager import ConfigManager


class InfoUtils:
    @staticmethod
    def get_user_nickname(
        config_manager: ConfigManager, sender: Mapping[str, object]
    ) -> str:
        """
        获取用户昵称

        优先使用nickname字段,如果为空则使用card(群名片)字段
        """
        enable_user_card = config_manager.get_enable_user_card()
        if enable_user_card:
            card = str(sender.get("card") or "")
            nickname = str(sender.get("nickname") or "")
            user_id = str(sender.get("user_id") or "")
            return card or nickname or user_id
        nickname = str(sender.get("nickname") or "")
        card = str(sender.get("card") or "")
        user_id = str(sender.get("user_id") or "")
        return nickname or card or user_id
