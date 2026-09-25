"""
OneBot 群文件与群相册管理器 (OneBot Group File & Album Manager)

负责处理 OneBot v11 平台的群文件上传、目录递归检索、文件夹创建及群相册扩展 API 调用。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .....utils.logger import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .....domain.repositories.bot_client_protocol import OneBotClientProtocol
    from .....domain.value_objects import OneBotAlbumPayload
    from .driver_base import OneBotDriver


class OneBotGroupFileManager:
    """OneBot 群文件与群相册功能管理器。"""

    bot: OneBotClientProtocol

    def __init__(
        self,
        bot: OneBotClientProtocol,
        driver_getter: Callable[[], Awaitable[OneBotDriver]],
        transmission_executor: Callable[..., Awaitable[bool]],
    ):
        """初始化群文件与相册管理器。

        Args:
            bot: OneBot 协议端客户端实例。
            driver_getter: 获取当前已探测绑定的 OneBotDriver 异步回调。
            transmission_executor: 执行 Base64/物理路径传输策略的异步回调。
        """
        self.bot = bot
        self._ensure_driver = driver_getter
        self._execute_transmission_strategy = transmission_executor

    async def upload_group_file_to_folder(
        self,
        group_id: str,
        file_path: str,
        filename: str | None = None,
        folder_id: str | None = None,
    ) -> bool:
        """上传文件到群文件目录的指定子文件夹。

        Args:
            group_id: 目标群号。
            file_path: 本地文件路径或 URL。
            filename: 上传后的文件名（若为空则使用原文件名）。
            folder_id: 目标群文件夹 ID（若为空则上传至根目录）。

        Returns:
            bool: 是否上传成功。
        """
        target_filename = filename or os.path.basename(file_path)
        logger.debug(
            f"[OneBot] 正在上传群文件 (群 {group_id}): 文件='{file_path}', "
            f"目标文件名='{target_filename}', 目标文件夹 ID='{folder_id}'"
        )

        async def do_upload(content: str, label: str):
            params: dict[str, object] = {
                "group_id": int(group_id),
                "file": content,
                "name": target_filename,
            }
            if folder_id:
                params["folder"] = folder_id
            await self.bot.call_action("upload_group_file", **params)
            logger.info(
                f"[OneBot] 群文件发送成功 ({label}): {params['name']} (群 {group_id})"
            )

        return await self._execute_transmission_strategy(
            file_path, do_upload, "OneBot 群文件"
        )

    async def create_group_file_folder(
        self,
        group_id: str,
        folder_name: str,
    ) -> str | None:
        """在群文件根目录下创建子文件夹。

        Args:
            group_id: 目标群号。
            folder_name: 文件夹名称。

        Returns:
            str | None: 创建成功时返回 folder_id，失败或已存在返回 None。
        """
        try:
            logger.debug(
                f"[OneBot] 正在群 {group_id} 中创建群文件夹 '{folder_name}'..."
            )
            result = await self.bot.call_action(
                "create_group_file_folder",
                group_id=int(group_id),
                name=folder_name,
                parent_id="/",
            )
            folder_id = None
            if isinstance(result, dict):
                data = result.get("data")
                if isinstance(data, dict):
                    folder_id = (
                        data.get("folder_id") or data.get("id") or data.get("folderId")
                    )
                elif isinstance(data, str) and data:
                    folder_id = data
                if not folder_id:
                    folder_id = (
                        result.get("folder_id")
                        or result.get("id")
                        or result.get("folderId")
                    )
            elif isinstance(result, str) and result:
                folder_id = result

            logger.info(
                f"[OneBot] 群文件夹创建成功: '{folder_name}' (群 {group_id})"
                + (f" [ID: {folder_id}]" if folder_id else "")
            )
            return str(folder_id) if folder_id is not None else None
        except Exception as e:
            error_msg = str(e).lower()
            if "exist" in error_msg or "已存在" in error_msg:
                logger.info(f"[OneBot] 群文件夹已存在: '{folder_name}' (群 {group_id})")
                return None
            logger.error(f"[OneBot] 群文件夹创建失败: {e}")
            return None

    async def get_group_file_root_folders(
        self,
        group_id: str,
    ) -> list[dict]:
        """获取群文件根目录下的文件夹列表。

        兼容顶层 folders、data.folders 及直接返回列表等多种 OneBot 实现规范。

        Args:
            group_id: 目标群号。

        Returns:
            list[dict]: 文件夹字典列表。
        """
        try:
            logger.debug(f"[OneBot] 正在获取群 {group_id} 的根目录文件夹列表...")
            result = await self.bot.call_action(
                "get_group_root_files",
                group_id=int(group_id),
            )
            folders: list[dict] = []
            if isinstance(result, list):
                folders = [f for f in result if isinstance(f, dict)]
            elif isinstance(result, dict):
                data = result.get("data")
                if isinstance(data, list):
                    folders = [f for f in data if isinstance(f, dict)]
                elif isinstance(data, dict):
                    raw_folders = (
                        data.get("folders")
                        or data.get("folder_list")
                        or data.get("folderList")
                        or data.get("list")
                    )
                    if isinstance(raw_folders, list):
                        folders = [f for f in raw_folders if isinstance(f, dict)]
                if not folders:
                    raw_folders = (
                        result.get("folders")
                        or result.get("folder_list")
                        or result.get("folderList")
                        or result.get("list")
                    )
                    if isinstance(raw_folders, list):
                        folders = [f for f in raw_folders if isinstance(f, dict)]

            logger.debug(
                f"[OneBot] 获取群文件夹列表成功 (群 {group_id}): 提取到 {len(folders)} 个文件夹"
            )
            return folders
        except Exception as e:
            logger.debug(f"[OneBot] 获取群文件夹列表失败 (群 {group_id}): {e}")
            return []

    async def find_or_create_folder(
        self,
        group_id: str,
        folder_name: str,
    ) -> str | None:
        """查找或创建指定名称的群文件子文件夹，返回 folder_id。

        Args:
            group_id: 目标群号。
            folder_name: 目标文件夹名称。

        Returns:
            str | None: 匹配或新创建的 folder_id，若均失败返回 None。
        """
        if not folder_name:
            return None

        target_name = str(folder_name).strip()
        logger.debug(
            f"[OneBot] 正在群 {group_id} 中查找或创建文件夹: '{target_name}'..."
        )

        # 1. 先尝试查找已有文件夹
        folders = await self.get_group_file_root_folders(group_id)
        for folder in folders:
            name = (
                folder.get("folder_name")
                or folder.get("name")
                or folder.get("folderName")
                or ""
            )
            fid = (
                folder.get("folder_id")
                or folder.get("id")
                or folder.get("folderId")
                or ""
            )
            if str(name).strip() == target_name and fid:
                logger.debug(
                    f"[OneBot] 匹配到已有群文件夹: '{target_name}' [ID: {fid}] (群 {group_id})"
                )
                return str(fid)

        # 2. 未找到，尝试创建
        created_id = await self.create_group_file_folder(group_id, target_name)
        if created_id:
            logger.info(
                f"[OneBot] 成功创建并获取到群文件夹 ID: '{target_name}' [ID: {created_id}] (群 {group_id})"
            )
            return str(created_id)

        # 3. 创建后再次查找（某些实现创建时不返回 ID）
        folders = await self.get_group_file_root_folders(group_id)
        for folder in folders:
            name = (
                folder.get("folder_name")
                or folder.get("name")
                or folder.get("folderName")
                or ""
            )
            fid = (
                folder.get("folder_id")
                or folder.get("id")
                or folder.get("folderId")
                or ""
            )
            if str(name).strip() == target_name and fid:
                logger.debug(
                    f"[OneBot] 创建后二次查询匹配到群文件夹: '{target_name}' [ID: {fid}] (群 {group_id})"
                )
                return str(fid)

        logger.warning(
            f"[OneBot] 无法获取群文件夹 ID: '{target_name}' (群 {group_id})，将上传到根目录"
        )
        return None

    async def upload_group_album(
        self,
        group_id: str,
        image_path: str,
        album_id: str | None = None,
        album_name: str | None = None,
        strict_mode: bool = False,
    ) -> bool:
        """上传图片到群相册。

        Args:
            group_id: 目标群号。
            image_path: 本地图片路径。
            album_id: 指定的相册 ID（可选）。
            album_name: 指定的相册名称（可选）。
            strict_mode: 是否启用严格模式（未找到相册时中止上传）。

        Returns:
            bool: 上传是否成功。
        """
        if not album_id and album_name:
            album_id = await self.find_album_id(group_id, album_name)

        if strict_mode and album_name and not album_id:
            logger.info(
                f"[群分析相册] 严格模式开启：未找到相册 '{album_name}' (群 {group_id})，停止上传。"
            )
            return False

        if not album_id:
            albums = await self.get_group_album_list(group_id)
            if albums:
                first = albums[0]
                album_id = (
                    first.get("album_id") or first.get("id") or first.get("albumId")
                )
                if album_name:
                    logger.info(
                        f"[群分析相册] 未找到相册 '{album_name}'，回退到默认相册 (群 {group_id})"
                    )

        if not album_id:
            logger.info(
                f"[群分析相册] 未能确定目标相册 (群 {group_id})，跳过相册上传。"
            )
            return False

        async def do_upload(content: str, label: str):
            driver = await self._ensure_driver()
            await driver.upload_group_album(
                bot=self.bot,
                group_id=group_id,
                album_id=str(album_id),
                album_name=album_name,
                file_content=content,
            )

        return await self._execute_transmission_strategy(
            image_path, do_upload, "OneBot 相册"
        )

    async def get_group_album_list(
        self,
        group_id: str,
    ) -> list[OneBotAlbumPayload]:
        """获取群相册列表。

        Args:
            group_id: 目标群号。

        Returns:
            list[OneBotAlbumPayload]: 相册字典列表。
        """
        driver = await self._ensure_driver()
        return await driver.get_group_album_list(self.bot, group_id)

    async def find_album_id(
        self,
        group_id: str,
        album_name: str,
    ) -> str | None:
        """根据相册名称查找 album_id。

        Args:
            group_id: 目标群号。
            album_name: 目标相册名称。

        Returns:
            str | None: 匹配的相册 ID，未找到返回 None。
        """
        if not album_name:
            return None

        target_name = str(album_name).strip()
        logger.debug(
            f"[群分析相册] 正在群 {group_id} 中查找名为 '{target_name}' 的相册..."
        )
        albums = await self.get_group_album_list(group_id)
        for album in albums:
            name = (
                album.get("name")
                or album.get("album_name")
                or album.get("albumName")
                or album.get("title")
            )
            aid = album.get("album_id") or album.get("id") or album.get("albumId")
            if name and str(name).strip() == target_name and aid is not None:
                logger.info(f"[群分析相册] 成功定位相册: '{target_name}' -> ID: {aid}")
                return str(aid)

        logger.info(f"[群分析相册] 未能找到名为 '{target_name}' 的相册 (群 {group_id})")
        return None
