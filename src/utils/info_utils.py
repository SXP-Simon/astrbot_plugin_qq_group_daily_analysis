class InfoUtils:
    @staticmethod
    def get_user_nickname(config_manager, sender) -> str:
        """
        获取用户昵称

        优先使用nickname字段，如果为空则使用card（群名片）字段
        """
        enable_user_card = config_manager.get_enable_user_card()
        if enable_user_card:
            return sender.get("card", "") or sender.get("nickname", "")
        else:
            return sender.get("nickname", "") or sender.get("card", "")
