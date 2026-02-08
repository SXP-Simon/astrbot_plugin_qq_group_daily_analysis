"""
常量 - 插件中使用的共享常量
"""

from enum import Enum


class Platform(str, Enum):
    """平台枚举类"""

    ONEBOT = "onebot"
    AIOCQHTTP = "aiocqhttp"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    LARK = "lark"


class TaskStatus(str, Enum):
    """任务状态枚举类"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ContentType(str, Enum):
    """消息内容类型枚举类"""

    TEXT = "text"
    IMAGE = "image"
    EMOJI = "emoji"
    STICKER = "sticker"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    REPLY = "reply"
    AT = "at"
    UNKNOWN = "unknown"


class ReportFormat(str, Enum):
    """报告格式枚举类"""

    TEXT = "text"
    MARKDOWN = "markdown"
    IMAGE = "image"
    HTML = "html"


# 插件元数据
PLUGIN_NAME = "astrbot_plugin_qq_group_daily_analysis"
PLUGIN_VERSION = "2.0.0"

# 平台标识符
PLATFORM_ONEBOT = "onebot"
PLATFORM_TELEGRAM = "telegram"
PLATFORM_DISCORD = "discord"
PLATFORM_SLACK = "slack"
PLATFORM_LARK = "lark"

SUPPORTED_PLATFORMS = [
    PLATFORM_ONEBOT,
    # 未来平台
    # PLATFORM_TELEGRAM,
    # PLATFORM_DISCORD,
    # PLATFORM_SLACK,
    # PLATFORM_LARK,
]

# 分析默认值
DEFAULT_MAX_TOPICS = 5
DEFAULT_MAX_USER_TITLES = 10
DEFAULT_MAX_GOLDEN_QUOTES = 5
DEFAULT_MIN_MESSAGES = 50
DEFAULT_MAX_TOKENS = 2000

# 时间段
HOUR_RANGES = {
    "morning": (6, 12),
    "afternoon": (12, 18),
    "evening": (18, 24),
    "night": (0, 6),
}

# 报告格式
REPORT_FORMAT_TEXT = "text"
REPORT_FORMAT_MARKDOWN = "markdown"
REPORT_FORMAT_IMAGE = "image"
REPORT_FORMAT_HTML = "html"

# 消息内容类型
CONTENT_TYPE_TEXT = "text"
CONTENT_TYPE_IMAGE = "image"
CONTENT_TYPE_EMOJI = "emoji"
CONTENT_TYPE_STICKER = "sticker"
CONTENT_TYPE_FILE = "file"
CONTENT_TYPE_AUDIO = "audio"
CONTENT_TYPE_VIDEO = "video"
CONTENT_TYPE_REPLY = "reply"
CONTENT_TYPE_AT = "at"
CONTENT_TYPE_UNKNOWN = "unknown"

# 分析任务状态
TASK_STATE_PENDING = "pending"
TASK_STATE_RUNNING = "running"
TASK_STATE_COMPLETED = "completed"
TASK_STATE_FAILED = "failed"
TASK_STATE_CANCELLED = "cancelled"

# 错误代码
ERROR_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
ERROR_LLM_FAILED = "LLM_FAILED"
ERROR_PLATFORM_ERROR = "PLATFORM_ERROR"
ERROR_CONFIG_ERROR = "CONFIG_ERROR"
ERROR_TIMEOUT = "TIMEOUT"

# 缓存 TTL（秒）
CACHE_TTL_SHORT = 60  # 1 分钟
CACHE_TTL_MEDIUM = 300  # 5 分钟
CACHE_TTL_LONG = 3600  # 1 小时
CACHE_TTL_DAY = 86400  # 24 小时

# 速率限制默认值
RATE_LIMIT_LLM_CALLS = 10  # 每分钟调用次数
RATE_LIMIT_API_CALLS = 60  # 每分钟调用次数
RATE_LIMIT_BURST = 5  # 突发大小

# 重试默认值
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 1.0
RETRY_MAX_DELAY = 30.0

# 文件路径
HISTORY_DIR = "history"
CACHE_DIR = "cache"
TEMP_DIR = "temp"
