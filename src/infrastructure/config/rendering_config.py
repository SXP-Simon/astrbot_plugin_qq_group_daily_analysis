"""可扩展图片渲染方案的配置契约与边界校验。"""

from collections.abc import Mapping
from typing import Literal, NotRequired, TypedDict
from urllib.parse import urlsplit

from ...shared.constants import DEFAULT_CDN_HOST
from ...utils.cdn_utils import normalize_cdn_base_url

CUSTOM_RESOURCE_OPTION = "__custom__"
DEFAULT_CUSTOM_T2I_ENDPOINT = "http://127.0.0.1:8999/text2img"
DEFAULT_CUSTOM_T2I_REQUEST_TIMEOUT_MS = 40000
FontMode = Literal["network", "local"]


class ScreenshotOptions(TypedDict, total=False):
    """插件交给宿主或自定义服务的截图选项，不包含地址和凭据。"""

    full_page: bool
    type: Literal["png", "jpeg"]
    quality: int
    device_scale_factor_level: Literal["normal", "high", "ultra"]
    timeout: int
    viewport_width: int
    viewport_height: int


class RenderingResourceConfig(TypedDict):
    """单轮资源地址快照；与具体截图服务无关。"""

    cdn_base_url: str
    google_fonts: str
    gstatic: str


DEFAULT_RENDERING_RESOURCES: dict[str, RenderingResourceConfig] = {
    "Mainland": {
        "cdn_base_url": DEFAULT_CDN_HOST,
        "google_fonts": "https://fonts.loli.net",
        "gstatic": "https://gstatic.loli.net",
    },
    "Overseas": {
        "cdn_base_url": DEFAULT_CDN_HOST,
        "google_fonts": "https://fonts.googleapis.com",
        "gstatic": "https://fonts.gstatic.com",
    },
}


class RenderingStrategyOptions(ScreenshotOptions, total=False):
    """运行时方案，服务与资源元数据在调用截图接口前移除。"""

    resource_environment: Literal["Mainland", "Overseas"]
    resource_urls: RenderingResourceConfig
    render_service: Literal["astrbot", "custom"]
    service_endpoint: str
    service_token: str
    request_timeout: int
    font_mode: FontMode


RenderingTemplateMarker = TypedDict(
    "RenderingTemplateMarker",
    {"__template_key": Literal["strategy", "mainland", "custom"]},
)


class RenderingStrategyPreset(RenderingTemplateMarker):
    """初始条目仅声明名称和顺序，资源在解析时补齐，避免覆盖旧地址。"""

    name: str
    priority: int


DEFAULT_RENDERING_STRATEGY_PRESETS: tuple[RenderingStrategyPreset, ...] = (
    {"__template_key": "strategy", "name": "海外方案", "priority": 10},
    {"__template_key": "mainland", "name": "内地方案", "priority": 20},
)


class RenderingStrategyConfig(RenderingResourceConfig, RenderingTemplateMarker):
    """配置面板中的单个渲染方案，数值越小越先执行。"""

    name: str
    priority: int
    environment: Literal["Mainland", "Overseas"]
    render_service: Literal["astrbot", "custom"]
    service_endpoint: str
    service_token: str
    type: Literal["png", "jpeg"]
    quality: int
    device_scale: Literal["normal", "high", "ultra"]
    timeout: int
    request_timeout: NotRequired[int]
    font_mode: NotRequired[FontMode]


def normalize_t2i_endpoint(value: str) -> str:
    """将兼容服务的根地址或生成接口统一为 /text2img 基础地址。

    Args:
        value: 用户填写的 HTTP(S) 服务地址。

    Returns:
        去除首尾空白、末尾斜杠和 /generate 的服务基础地址。

    Raises:
        ValueError: 地址为空、格式无效，或包含认证信息、查询参数和片段。
    """
    error = "请填写完整的 T2I 服务地址，例如 http://127.0.0.1:8999/text2img，不要带账号密码、查询参数或 # 片段"
    if len(value) > 2048:
        raise ValueError(error)
    value = value.strip().rstrip("/")
    if (
        not value
        or any(char.isspace() or not char.isprintable() for char in value)
        or any(char in value for char in "?#\\")
    ):
        raise ValueError(error)
    try:
        parsed = urlsplit(value)
        origin = normalize_cdn_base_url(f"{parsed.scheme}://{parsed.netloc}")
    except ValueError as exc:
        raise ValueError(error) from exc
    path = parsed.path.rstrip("/")
    if path.endswith("/text2img/generate"):
        path = path.removesuffix("/generate")
    if not path.endswith("/text2img"):
        path += "/text2img"
    return origin + path


def parse_rendering_strategies(
    value: object, legacy_config: Mapping[str, object] | None = None
) -> list[RenderingStrategyConfig]:
    """校验方案列表并按优先级稳定排序，不修改输入，运行时只读取已声明字段。

    Args:
        value: 配置文件或保存请求中的方案列表。
        legacy_config: 旧环境级资源地址，仅在方案没有对应字段时继承。

    Returns:
        供运行时使用的规范化方案；相同优先级保持原列表顺序。

    Raises:
        ValueError: 列表、方案字段或参数范围无效。
    """
    if not isinstance(value, list):
        raise ValueError("渲染方案必须是列表")
    result: list[RenderingStrategyConfig] = []
    for index, item in enumerate(value, 1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 个渲染方案必须是配置对象")
        name = item.get("name", "渲染方案")
        environment = item.get(
            "environment",
            "Mainland" if item.get("__template_key") == "mainland" else "Overseas",
        )
        render_service = item.get(
            "render_service",
            "custom" if item.get("__template_key") == "custom" else "astrbot",
        )
        endpoint = item.get(
            "service_endpoint",
            DEFAULT_CUSTOM_T2I_ENDPOINT if render_service == "custom" else "",
        )
        token = item.get("service_token", "")
        image_type = item.get("type", "png")
        scale = item.get("device_scale", "high")
        if not isinstance(name, str):
            raise ValueError(f"第 {index} 个渲染方案的名称必须是文字")
        if environment not in ("Mainland", "Overseas"):
            raise ValueError(f"第 {index} 个渲染方案请选择内地或海外环境")
        if render_service not in ("astrbot", "custom"):
            raise ValueError(f"第 {index} 个渲染方案请选择跟随 AstrBot 或自定义服务")
        if not isinstance(endpoint, str):
            raise ValueError(f"第 {index} 个渲染方案的服务地址必须是文字")
        if (
            not isinstance(token, str)
            or len(token) > 4096
            or not token.isascii()
            or any(not char.isprintable() for char in token)
        ):
            raise ValueError(
                f"第 {index} 个渲染方案的服务 Token 请使用英文、数字或常用符号，不能换行，长度不能超过 4096 个字符"
            )
        endpoint = endpoint.strip()
        if render_service == "custom":
            endpoint = normalize_t2i_endpoint(endpoint)
        if image_type not in ("png", "jpeg"):
            raise ValueError(f"第 {index} 个渲染方案请选择 PNG 或 JPEG 格式")
        if scale not in ("normal", "high", "ultra"):
            raise ValueError(f"第 {index} 个渲染方案的分辨率等级无效")
        defaults = DEFAULT_RENDERING_RESOURCES[environment]
        resources: dict[str, str] = {}
        for key, label in (
            ("cdn_base_url", "模板资源 CDN"),
            ("google_fonts", "Google Fonts 地址"),
            ("gstatic", "字体文件地址"),
        ):
            candidate = item.get(key)
            if candidate == CUSTOM_RESOURCE_OPTION:
                candidate = item.get(f"custom_{key}")
                if not isinstance(candidate, str) or not candidate.strip():
                    raise ValueError(f"第 {index} 个渲染方案请填写自定义{label}")
            if key not in item and legacy_config is not None:
                candidate = legacy_config.get(f"t2i_{environment.lower()}_{key}")
                if key == "cdn_base_url" and (
                    candidate is None
                    or (isinstance(candidate, str) and not candidate.strip())
                ):
                    candidate = legacy_config.get("t2i_cdn_base_url")
            try:
                if candidate is None and key not in item:
                    candidate = defaults[key]
                if not isinstance(candidate, str):
                    raise ValueError("地址必须是文字")
                if len(candidate) > 2048:
                    raise ValueError("地址不能超过 2048 个字符")
                candidate = candidate.strip()
                if not candidate:
                    candidate = defaults[key]
                if key == "cdn_base_url":
                    candidate = normalize_cdn_base_url(candidate)
                else:
                    parsed = urlsplit(candidate)
                    origin = normalize_cdn_base_url(
                        f"{parsed.scheme}://{parsed.netloc}"
                    )
                    if len(candidate) > 2048 or any(
                        ch.isspace() or not ch.isprintable() or ch in "?#\\"
                        for ch in candidate
                    ):
                        raise ValueError("字体地址格式无效")
                    candidate = origin + parsed.path.rstrip("/")
                resources[key] = candidate
            except ValueError as exc:
                if key in item:
                    raise ValueError(
                        f"第 {index} 个渲染方案的{label}无效，请填写完整的 HTTP(S) 地址"
                    ) from exc
                # 旧字段只负责兼容读取，无效值沿用环境默认地址。
                resources[key] = defaults[key]
        integers = {}
        for key, label, default, lower, upper in (
            ("priority", "优先级", 10, 0, 10000),
            ("quality", "图片质量", 80, 1, 100),
            ("timeout", "渲染超时", 20000, 1000, 300000),
        ):
            number = item.get(key, default)
            if type(number) is not int or not lower <= number <= upper:
                raise ValueError(
                    f"第 {index} 个渲染方案的{label} 必须是 {lower} 到 {upper} 的整数"
                )
            integers[key] = number
        plan: RenderingStrategyConfig = {
            "__template_key": (
                "custom"
                if render_service == "custom"
                else "mainland"
                if environment == "Mainland"
                else "strategy"
            ),
            "cdn_base_url": resources["cdn_base_url"],
            "google_fonts": resources["google_fonts"],
            "gstatic": resources["gstatic"],
            "name": name,
            "priority": integers["priority"],
            "environment": environment,
            "render_service": render_service,
            "service_endpoint": endpoint,
            "service_token": token.strip(),
            "type": image_type,
            "quality": integers["quality"],
            "device_scale": scale,
            "timeout": integers["timeout"],
        }
        if render_service == "custom" or "request_timeout" in item:
            request_timeout = item.get(
                "request_timeout", DEFAULT_CUSTOM_T2I_REQUEST_TIMEOUT_MS
            )
            if (
                type(request_timeout) is not int
                or not 1000 <= request_timeout <= 300000
            ):
                raise ValueError(
                    f"第 {index} 个渲染方案的请求等待上限必须是 1000 到 300000 的整数"
                )
            plan["request_timeout"] = request_timeout
        if render_service == "custom":
            font_mode = item.get("font_mode", "network")
            if font_mode not in ("network", "local"):
                raise ValueError(f"第 {index} 个渲染方案请选择在线字体或已安装字体")
            plan["font_mode"] = font_mode
        result.append(plan)
    return sorted(result, key=lambda strategy: strategy["priority"])
