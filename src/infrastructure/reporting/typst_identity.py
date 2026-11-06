"""Request-scoped identity privacy, nickname resolution and avatar localization."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from .display_names import normalize_display_name
from .render_data_preparer import RenderDataPreparer

if TYPE_CHECKING:
    from ...domain.value_objects import AnalysisResultPayload
    from .avatar_service import AvatarService
    from .typst_contracts import TextRun, TypstIdentityOptions
    from .typst_images import TypstAssets


class TypstIdentityResolver:
    """Resolve identities once per report while preserving platform isolation."""

    def __init__(
        self,
        avatars: AvatarService,
        assets: TypstAssets,
        result: AnalysisResultPayload,
        identity: TypstIdentityOptions,
    ) -> None:
        self.avatars, self.assets = avatars, assets
        self._avatar_cache: dict[tuple[str, bool], str] = {}
        self._name_cache: dict[str, str] = {}
        users = dict(result.get("user_analysis") or {})
        for portrait in result["user_titles"]:
            users.setdefault(str(portrait.user_id), {"nickname": portrait.name})
        for quote in result["statistics"].golden_quotes:
            if quote.user_id:
                users.setdefault(str(quote.user_id), {"nickname": quote.sender})
        self.result: AnalysisResultPayload = {**result, "user_analysis": users}
        self.hide_names, self.extended_ids = identity.hide_names, identity.extended_ids
        self.avatar_getter, self.nickname_getter, self.namespace = (
            identity.avatar_getter,
            identity.nickname_getter,
            identity.namespace,
        )

    def plain(self, text: str) -> str:
        """净化标题、名称和多处正文片段中的身份信息。

        Args:
            text: 原始展示文本。

        Returns:
            匿名模式下移除已知身份的普通文本。
        """
        return RenderDataPreparer.sanitize_identity_text(
            text, self.result, self.hide_names
        )

    async def avatar(self, user_id: str, *, oval: bool = False) -> str:
        """通过平台隔离头像缓存获取并本地化头像。

        Args:
            user_id: 仅在准备阶段使用的身份编号。
            oval: 是否采用 Maria 椭圆肖像；正文提及仍使用圆形头像。

        Returns:
            本次编译目录内的头像路径。
        """
        if not user_id:
            return ""
        key = (user_id, oval)
        if key in self._avatar_cache:
            return self._avatar_cache[key]
        try:
            async with asyncio.timeout_at(self.assets.network_deadline):
                source = await self.avatars.get_user_avatar(
                    user_id, self.avatar_getter, self.namespace
                )
        except TimeoutError:
            self.assets.network_budget_exhausted = True
            return ""
        localized = await self.assets.localize(source, oval=oval)
        self._avatar_cache[key] = localized
        return localized

    async def rich_text(self, text: str) -> list[TextRun]:
        """将话题、金句和评价中的引用转为头像片段，不执行输入中的标记。

        Args:
            text: 含方括号用户引用或普通文本的内容。

        Returns:
            有顺序的普通文本与用户引用；匿名引用只保留头像。
        """
        users = self.result["user_analysis"]
        source = str(text)
        extended = self.hide_names or self.extended_ids
        if extended:
            for uid in sorted(users, key=len, reverse=True):
                source = re.sub(
                    rf"(?<!\[)(?<![A-Za-z0-9_-]){re.escape(uid)}(?![A-Za-z0-9_-])(?!\])",
                    f"[{uid}]",
                    source,
                )
        pattern = r"\[([A-Za-z0-9_-]{1,128})\]" if extended else r"\[(\d+)\]"
        runs: list[TextRun] = []
        position = 0
        for match in re.finditer(pattern, source):
            uid = match.group(1)
            if extended and uid not in users:
                continue
            runs.append(
                {"text": self.plain(source[position : match.start()]), "avatar": ""}
            )
            name = await self._user_name(uid)
            runs.append(
                {
                    "text": "" if self.hide_names else name,
                    "avatar": await self.avatar(uid),
                }
            )
            position = match.end()
        runs.append({"text": self.plain(source[position:]), "avatar": ""})
        return runs

    async def _user_name(self, uid: str) -> str:
        """在可选网络预算内查询昵称，超时仍保留原有身份占位规则。

        Args:
            uid: 当前提及的成员编号。

        Returns:
            可展示昵称，或原有的群友/编号占位文字。
        """
        if uid in self._name_cache:
            return self._name_cache[uid]
        stats = self.result["user_analysis"].get(uid)
        name = (
            normalize_display_name(
                str(stats.get("nickname") or stats.get("name") or "")
            )
            if isinstance(stats, dict)
            else ""
        )
        if not name and self.nickname_getter and not self.hide_names:
            try:
                async with asyncio.timeout_at(self.assets.network_deadline):
                    name = normalize_display_name(
                        str(await self.nickname_getter(uid) or "")
                    )
            except TimeoutError:
                self.assets.network_budget_exhausted = True
            except Exception:
                name = ""
        if RenderDataPreparer.is_placeholder_display_name(name, uid):
            name = "群友" if self.extended_ids else uid
        self._name_cache[uid] = name
        return name
