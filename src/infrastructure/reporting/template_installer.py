"""
模板安装器 - 自第三方安装自定义报告视觉模板

支持两种来源：
- GitHub 仓库链接（github.com/<owner>/<repo>，可选 /tree/<branch>），以源码 ZIP 下载后安装；
- 用户上传的 zip 压缩包（JSON Base64 方式，与插件既有 config/upload_file 一致）。

安装目标是插件数据目录下的 custom_t2i_templates/reporting_templates/<模板名>/，
与 ConfigManager.get_custom_report_template_dir 读取的目录完全一致，安装完成即被
HTMLTemplates 动态发现，无需重启机器人。

命名仅做安全校验（非空、长度、无路径分隔符与文件系统危险字符），不强制风格与前缀。
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from ...shared.constants import PLUGIN_NAME
from ...utils.logger import logger

IMAGE_TEMPLATE_MARKER = "image_template.html"
HTML_TEMPLATE_MARKER = "html_template.html"
TEMPLATE_META_FILENAME = "template.json"  # 可选: {"name": "显示名"}
# 安装器写入的安装标记：用于区分“通过插件安装器下载的模板”与“手动放入的目录”，
# 只有带此标记的模板才允许通过 WebUI 自动卸载。
INSTALL_MARKER_FILENAME = ".tpl_installed.json"

MAX_TEMPLATE_NAME_LEN = 50
MAX_ARCHIVE_MEMBERS = 300
MAX_ARCHIVE_TOTAL_SIZE = 64 * 1024 * 1024  # 解压后总大小上限
MAX_SINGLE_FILE_SIZE = 20 * 1024 * 1024
MAX_DOWNLOAD_SIZE = 64 * 1024 * 1024
MAX_ZIP_B64_SIZE = 80 * 1024 * 1024

# 模板名中禁止的字符：路径分隔符与 Windows/Linux 文件名危险字符（允许中文等任意其余字符）
_INVALID_NAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

_GITHUB_HOSTS = {"github.com", "www.github.com"}


class TemplateInstallError(Exception):
    """模板安装失败（用户可读的错误信息）。"""


def default_template_store_dir() -> Path:
    """返回用户自定义报告模板存储根目录（与 ConfigManager 读取路径一致）。"""
    data_dir = Path.cwd() / "data" / "plugin_data" / PLUGIN_NAME
    try:
        from astrbot.api.star import StarTools

        got = StarTools.get_data_dir(PLUGIN_NAME)
        if got:
            data_dir = Path(str(got))
    except Exception:
        pass
    return data_dir / "custom_t2i_templates" / "reporting_templates"


def builtin_template_names() -> list[str]:
    """返回内置模板目录名列表（用于重名冲突检测）。"""
    base_dir = Path(__file__).resolve().parent / "templates"
    names: list[str] = []
    if base_dir.is_dir():
        names = [
            entry
            for entry in os.listdir(base_dir)
            if (base_dir / entry).is_dir() and not entry.startswith(".")
        ]
    return names


def validate_template_name(name: str) -> str:
    """校验并规范化模板名。仅做安全校验，不约束命名风格。"""
    if not isinstance(name, str) or not name.strip():
        raise TemplateInstallError("模板名不能为空。")
    cleaned = name.strip()
    if cleaned in {".", ".."}:
        raise TemplateInstallError(f"模板名 '{cleaned}' 非法。")
    if cleaned.startswith(".") or cleaned.endswith("."):
        raise TemplateInstallError("模板名不能以点开头或结尾。")
    if len(cleaned) > MAX_TEMPLATE_NAME_LEN:
        raise TemplateInstallError(
            f"模板名过长（{len(cleaned)} > {MAX_TEMPLATE_NAME_LEN} 字符）。"
        )
    if _INVALID_NAME_CHARS.search(cleaned):
        raise TemplateInstallError(
            '模板名包含非法字符（路径分隔符或 \\ / : * ? " < > | 等）。'
        )
    return cleaned


def _assert_target_free(store_dir: Path, name: str) -> None:
    """目标模板目录不得已存在，且不得与内置模板重名。"""
    if name in builtin_template_names():
        raise TemplateInstallError(
            f"模板名 '{name}' 与内置模板重名，请换个名字（例如 {name}_custom）。"
        )
    target = store_dir / name
    if target.exists():
        raise TemplateInstallError(
            f"模板 '{name}' 已存在，请换个名字（或手动删除数据目录中的同名文件夹）。"
        )


def _validate_archive_members(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """校验压缩包成员的安全性与规模（防 zip-slip / 路径穿越 / 压缩炸弹）。"""
    members = zf.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise TemplateInstallError(
            f"压缩包文件过多（{len(members)} > {MAX_ARCHIVE_MEMBERS}）。"
        )
    total_size = 0
    for member in members:
        norm = member.filename.replace("\\", "/")
        if any(ord(ch) < 32 for ch in member.filename):
            raise TemplateInstallError(f"压缩包包含控制字符的文件名: {member.filename!r}")
        if (
            norm.startswith("/")
            or norm.startswith("//")
            or re.match(r"^[A-Za-z]:", norm)
        ):
            raise TemplateInstallError(f"压缩包包含非法绝对路径: {member.filename}")
        parts = norm.split("/")
        if any(part in {".", ".."} for part in parts):
            raise TemplateInstallError(f"压缩包包含非法路径段: {member.filename}")
        if member.file_size > MAX_SINGLE_FILE_SIZE:
            raise TemplateInstallError(
                f"压缩包内文件过大（{member.filename}）。"
            )
        total_size += member.file_size
        if total_size > MAX_ARCHIVE_TOTAL_SIZE:
            raise TemplateInstallError("压缩包解压后总大小超出限制。")
    return members


def _locate_template_root(members: list[zipfile.ZipInfo]) -> str:
    """在压缩包中定位模板根目录（zip 内相对路径，'' 表示顶层）。

    优先取最浅的、包含 image_template.html 或 html_template.html 的目录。
    """
    marker_dirs: dict[str, tuple[str, int]] = {}
    for member in members:
        if member.is_dir():
            continue
        norm = member.filename.replace("\\", "/")
        filename = norm.rsplit("/", 1)[-1]
        if filename not in {IMAGE_TEMPLATE_MARKER, HTML_TEMPLATE_MARKER}:
            continue
        directory = norm.rsplit("/", 1)[0] if "/" in norm else ""
        depth = 0 if not directory else directory.count("/") + 1
        marker_dirs[directory] = (member.filename, depth)

    if not marker_dirs:
        raise TemplateInstallError(
            "压缩包中未找到模板主文件（image_template.html 或 html_template.html）。"
        )

    min_depth = min(depth for _, (_, depth) in marker_dirs.items())
    shallowest = [
        directory
        for directory, (_, depth) in marker_dirs.items()
        if depth == min_depth
    ]
    if len(shallowest) > 1:
        raise TemplateInstallError(
            "压缩包中可能存在多个模板目录，请将单个模板独立打包后再安装。"
        )
    return shallowest[0]


def _extract_template_root(
    zf: zipfile.ZipFile,
    root: str,
    extract_dir: Path,
) -> list[str]:
    """将模板根目录下的文件安全地写入目标目录，返回写入的文件名列表。"""
    written: list[str] = []
    root_prefix = root + "/" if root else ""
    for member in zf.infolist():
        if member.is_dir():
            continue
        norm = member.filename.replace("\\", "/")
        if root_prefix:
            if norm == root:
                continue
            if not norm.startswith(root_prefix):
                continue  # 忽略模板根目录之外的冗余文件
            rel = norm[len(root_prefix) :]
        else:
            rel = norm
        if not rel:
            continue
        dest = (extract_dir / rel).resolve()
        # 双重保险：成员已通过 _validate_archive_members 路径段校验，
        # 此处再确保实际写入路径仍位于临时目录之内（commonpath + normcase 兼容 Windows）。
        base_real = os.path.normcase(str(extract_dir.resolve()))
        if os.path.normcase(os.path.commonpath([str(dest), base_real])) != base_real:
            raise TemplateInstallError(f"非法解压路径: {member.filename}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with zf.open(member) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out, length=1024 * 1024)
        except (RuntimeError, NotImplementedError) as exc:
            raise TemplateInstallError(
                "压缩包无法解压（可能已加密或使用了不支持的压缩算法）。"
            ) from exc
        written.append(rel)
    return written


def _read_template_meta(extract_dir: Path) -> dict[str, Any]:
    """读取可选的 template.json 元信息（仅取 name/desc 字符串）。"""
    meta_path = extract_dir / TEMPLATE_META_FILENAME
    if not meta_path.is_file():
        return {}
    try:
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning(f"模板元信息 {TEMPLATE_META_FILENAME} 解析失败，已忽略。")
        return {}
    meta: dict[str, Any] = {}
    for key in ("name", "desc"):
        value = raw.get(key) if isinstance(raw, dict) else None
        if isinstance(value, str) and value.strip():
            meta[key] = value.strip()[:100]
    return meta


def _write_install_marker(target_dir: Path, *, source: str, source_url: str) -> None:
    """写入安装标记文件（卸载权限的依据）。"""
    payload = {
        "installed_by": PLUGIN_NAME,
        "source": source,
        "source_url": source_url,
        "installed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        (target_dir / INSTALL_MARKER_FILENAME).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning(f"写入安装标记失败: {exc}")


def install_template_from_zip(
    zip_data: bytes,
    store_dir: Path | None = None,
    name: str | None = None,
    source: str = "upload",
    source_url: str = "",
) -> dict[str, Any]:
    """从 zip 字节安装模板。

    Args:
        zip_data: zip 文件内容。
        store_dir: 自定义模板存储根目录；None 时使用插件数据目录。
        name: 期望的模板名；None 时从压缩包根目录名 / 内容推导。

    Returns:
        安装结果字典: name / label / has_image / has_html / files。
    """
    if not zip_data:
        raise TemplateInstallError("压缩包内容为空。")
    store = store_dir or default_template_store_dir()
    store.mkdir(parents=True, exist_ok=True)

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_data))
    except zipfile.BadZipFile as exc:
        raise TemplateInstallError("压缩包格式无效，请确认上传的是 zip 文件。") from exc

    with zf:
        members = _validate_archive_members(zf)
        root = _locate_template_root(members)

        # 推导候选模板名：压缩包根目录名（去掉 GitHub archive 的 -main/-master 后缀）
        # → 用户提供名 → 报错
        derived = ""
        if root:
            derived = root.rsplit("/", 1)[-1]
            for suffix in ("-main", "-master"):
                if derived.endswith(suffix) and len(derived) > len(suffix):
                    derived = derived[: -len(suffix)]
                    break
        if name:
            template_name = validate_template_name(name)
        elif derived:
            template_name = validate_template_name(derived)
        else:
            raise TemplateInstallError(
                "无法从压缩包推断模板名，请手动指定模板名。"
            )

        _assert_target_free(store, template_name)

        with tempfile.TemporaryDirectory(prefix="tpl_install_") as tmp:
            extract_dir = Path(tmp)
            written = _extract_template_root(zf, root, extract_dir)

            has_image = (extract_dir / IMAGE_TEMPLATE_MARKER).is_file()
            has_html = (extract_dir / HTML_TEMPLATE_MARKER).is_file()
            meta = _read_template_meta(extract_dir)

            # 校验主模板文件（与 HTMLTemplates 识别规则一致）
            if not has_image and not has_html:
                raise TemplateInstallError(
                    "模板根目录下缺少 image_template.html / html_template.html。"
                )

            target = store / template_name
            target.mkdir(parents=True, exist_ok=True)
            try:
                for rel in written:
                    src_file = extract_dir / rel
                    dest_file = target / rel
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    # 用 shutil.move（而非 os.replace）：临时目录与插件数据目录可能位于不同
                    # 文件系统/磁盘，os.replace 跨设备会抛 EXDEV，shutil.move 自动降级为复制。
                    shutil.move(str(src_file), str(dest_file))
            except Exception:
                shutil.rmtree(target, ignore_errors=True)
                raise

            _write_install_marker(target, source=source, source_url=source_url)

    label = meta.get("name") or template_name
    logger.info(
        f"模板安装成功: {template_name} (label={label}) "
        f"files={len(written)} has_image={has_image} has_html={has_html}"
    )
    return {
        "name": template_name,
        "label": label,
        "desc": meta.get("desc", ""),
        "has_image": has_image,
        "has_html": has_html,
        "files": sorted(written),
    }


def parse_github_repo_url(repo_url: str) -> dict[str, str]:
    """解析 GitHub 仓库链接。

    仅支持 github.com（含 www），路径形式：
    - /<owner>/<repo>（可带 .git）
    - /<owner>/<repo>/tree/<branch>

    Returns:
        包含 owner/repo/branch/default_name 的字典。
    """
    if not isinstance(repo_url, str) or not repo_url.strip():
        raise TemplateInstallError("GitHub 链接不能为空。")
    url = repo_url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise TemplateInstallError("仅支持 http/https 链接。")
    if parsed.hostname not in _GITHUB_HOSTS:
        raise TemplateInstallError("仅支持 github.com 仓库链接。")

    parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise TemplateInstallError("GitHub 链接格式不正确。")

    owner, repo = parts[0], parts[1].removesuffix(".git")
    if not owner or not repo or owner in {".", ".."} or repo in {".", ".."}:
        raise TemplateInstallError("GitHub 链接格式不正确。")
    if not re.match(r"^[A-Za-z0-9_.-]+$", owner) or not re.match(
        r"^[A-Za-z0-9_.-]+$", repo
    ):
        raise TemplateInstallError("GitHub 链接包含非法字符。")

    branch = ""
    if len(parts) == 2:
        branch = ""
    elif len(parts) >= 4 and parts[2] == "tree":
        branch_parts = parts[3:]
        if any(
            not re.match(r"^[A-Za-z0-9._-]+$", seg) or seg in {".", ".."}
            for seg in branch_parts
        ):
            raise TemplateInstallError("GitHub 分支名包含非法字符。")
        branch = "/".join(branch_parts)
    else:
        raise TemplateInstallError("仅支持仓库主页或 /tree/<分支> 形式的链接。")

    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "default_name": repo,
    }


async def _resolve_default_branch(session: Any, owner: str, repo: str) -> str:
    """通过 GitHub API 获取默认分支；失败时返回空串由调用方回退。"""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        async with session.get(url, timeout=aiohttp_client_timeout(10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                branch = str(data.get("default_branch") or "").strip()
                if branch:
                    return branch
    except Exception as exc:
        logger.debug(f"获取 {owner}/{repo} 默认分支失败: {exc}")
    return ""


def aiohttp_client_timeout(seconds: float) -> Any:
    """构造 aiohttp 超时对象（延迟导入，避免模块加载时依赖 aiohttp）。"""
    import aiohttp

    return aiohttp.ClientTimeout(total=seconds)


def _archive_url_candidates(resolved_branch: str) -> list[str]:
    """根据解析结果生成待尝试的归档分支候选。

    规则：
    - 用户显式指定了分支（含 /tree/<分支> 形式）：只尝试该分支，静默回退会违背用户预期；
    - GitHub API 解析成功：只尝试解析出的默认分支；
    - API 不可用（返回空）：依次回退 main → master。
    """
    if resolved_branch:
        return [resolved_branch]
    return ["main", "master"]


async def download_github_archive(
    owner: str,
    repo: str,
    branch: str = "",
) -> bytes:
    """下载 GitHub 源码 ZIP。分支未指定时先查默认分支，失败后回退 main/master。"""
    import aiohttp

    async with aiohttp.ClientSession(trust_env=True) as session:
        resolved = branch
        if not resolved:
            resolved = await _resolve_default_branch(session, owner, repo)
        candidates = _archive_url_candidates(resolved)

        last_error = ""
        for candidate in candidates:
            url = (
                f"https://github.com/{owner}/{repo}/archive/"
                f"refs/heads/{candidate}.zip"
            )
            logger.info(f"下载模板压缩包: {url}")
            try:
                async with session.get(url, timeout=aiohttp_client_timeout(120)) as resp:
                    if resp.status != 200:
                        last_error = f"下载失败 (HTTP {resp.status}): {url}"
                        continue
                    # 流式下载并限制大小：先查 Content-Length，读取时再累计兜底
                    declared = resp.headers.get("Content-Length")
                    if declared and declared.isdigit() and int(declared) > MAX_DOWNLOAD_SIZE:
                        raise TemplateInstallError(
                            "下载的压缩包超出大小限制（64MB）。"
                        )
                    body = bytearray()
                    async for chunk in resp.content.iter_chunked(64 * 1024):
                        body.extend(chunk)
                        if len(body) > MAX_DOWNLOAD_SIZE:
                            raise TemplateInstallError(
                                "下载的压缩包超出大小限制（64MB）。"
                            )
                    if not body:
                        raise TemplateInstallError("下载的压缩包为空。")
                    return bytes(body)
            except TemplateInstallError:
                raise
            except Exception as exc:
                last_error = f"下载异常: {exc}"

    raise TemplateInstallError(
        last_error or f"无法下载 {owner}/{repo} 的压缩包。"
    )


def uninstall_template(
    name: str,
    store_dir: Path | None = None,
) -> dict[str, Any]:
    """卸载通过插件安装器下载的自定义模板。

    仅允许卸载带安装标记（.tpl_installed.json）的模板：
    - 内置模板（位于插件内置 templates 目录）不在此目录下，且按名字直接拒绝；
    - 手动放入数据目录、未经安装器安装的目录无标记，拒绝自动卸载。

    Args:
        name: 模板目录名。
        store_dir: 自定义模板存储根目录；None 时使用插件数据目录。

    Returns:
        卸载结果字典: name / removed。
    """
    template_name = validate_template_name(name)
    if template_name in builtin_template_names():
        raise TemplateInstallError(
            f"模板 '{template_name}' 是内置模板，不支持卸载。"
        )
    store = store_dir or default_template_store_dir()
    base_real = os.path.normcase(str(store.resolve()))
    raw_target = store / template_name
    # 拒绝符号链接目标：rmtree 对指向目录的链接（Linux 上常见）会删除链接所指内容，
    # resolve() 无法区分“合法目录”与“指向同目录下其他位置的链接”。
    if raw_target.is_symlink():
        raise TemplateInstallError("模板名非法。")
    target = raw_target.resolve()
    try:
        on_base = os.path.normcase(
            os.path.commonpath([str(target), base_real])
        ) == base_real
    except ValueError:
        # Windows 下 commonpath 对不同驱动器的路径会抛 ValueError
        on_base = False
    if not on_base:
        raise TemplateInstallError("模板名非法。")
    if not target.is_dir():
        raise TemplateInstallError(f"模板 '{template_name}' 不存在。")
    if not (target / INSTALL_MARKER_FILENAME).is_file():
        raise TemplateInstallError(
            f"模板 '{template_name}' 不是通过插件安装器下载的，无法自动卸载；"
            "如需移除请手动删除数据目录下的同名文件夹。"
        )

    try:
        shutil.rmtree(target)
    except Exception as exc:
        raise TemplateInstallError(
            f"卸载模板 '{template_name}' 失败：{exc}"
        ) from exc
    logger.info(f"模板已卸载: {template_name}")
    return {"name": template_name, "removed": True}


async def install_template_from_github_url(
    repo_url: str,
    store_dir: Path | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """从 GitHub 仓库链接安装模板（异步：下载 + 解压安装）。"""
    parsed = parse_github_repo_url(repo_url)
    zip_data = await download_github_archive(
        parsed["owner"], parsed["repo"], parsed["branch"]
    )
    return install_template_from_zip(
        zip_data, store_dir=store_dir, name=name, source="url", source_url=repo_url
    )
