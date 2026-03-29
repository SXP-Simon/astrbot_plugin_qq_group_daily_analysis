from collections.abc import Mapping
from typing import Protocol


class _SupportsUserCardConfig(Protocol):
    def get_enable_user_card(self) -> bool: ...


class InfoUtils:
    @staticmethod
    def get_user_nickname(
        config_manager: _SupportsUserCardConfig,
        sender: Mapping[str, object],
    ) -> str:
        """
        获取用户昵称

        优先使用nickname字段,如果为空则使用card(群名片)字段
        """
        enable_user_card = config_manager.get_enable_user_card()
        card = str(sender.get("card", "") or "")
        nickname = str(sender.get("nickname", "") or "")
        user_id = str(sender.get("user_id", "") or "")

        if enable_user_card:
            return card or nickname or user_id
        else:
            return nickname or card or user_id
