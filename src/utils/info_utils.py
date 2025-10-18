class InfoUtils:
    @staticmethod
    def get_user_nickname(sender) -> str:
        """
        获取用户昵称

        优先使用nickname字段，如果为空则使用card（群名片）字段
        """
        return sender.get("nickname", "") or sender.get("card", "")
