"""
领域异常 - 领域层自定义异常

该模块包含插件中使用的所有领域特定异常。
这些异常是平台无关的，表示业务逻辑错误。
"""


class DomainException(Exception):
    """所有领域错误的基础异常。"""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


# ============================================================================
# 分析异常
# ============================================================================


class AnalysisException(DomainException):
    """分析相关错误的基础异常。"""

    def __init__(self, message: str, code: str = "ANALYSIS_ERROR"):
        super().__init__(message, code)


class InsufficientDataException(AnalysisException):
    """当数据不足以进行分析时抛出。"""

    def __init__(self, message: str = "数据不足，无法进行分析"):
        super().__init__(message, "INSUFFICIENT_DATA")


class AnalysisTimeoutException(AnalysisException):
    """当分析超时时抛出。"""

    def __init__(self, message: str = "分析超时"):
        super().__init__(message, "ANALYSIS_TIMEOUT")


class LLMException(AnalysisException):
    """当 LLM API 调用失败时抛出。"""

    def __init__(self, message: str = "LLM API 调用失败", provider: str = ""):
        self.provider = provider
        super().__init__(f"{message} (提供商: {provider})" if provider else message, "LLM_ERROR")


class LLMRateLimitException(LLMException):
    """当 LLM API 速率限制超出时抛出。"""

    def __init__(self, message: str = "LLM 速率限制超出", provider: str = ""):
        super().__init__(message, provider)
        self.code = "LLM_RATE_LIMIT"


class LLMQuotaExceededException(LLMException):
    """当 LLM API 配额超出时抛出。"""

    def __init__(self, message: str = "LLM 配额超出", provider: str = ""):
        super().__init__(message, provider)
        self.code = "LLM_QUOTA_EXCEEDED"


# ============================================================================
# 平台异常
# ============================================================================


class PlatformException(DomainException):
    """平台相关错误的基础异常。"""

    def __init__(self, message: str, platform: str = "", code: str = "PLATFORM_ERROR"):
        self.platform = platform
        super().__init__(f"[{platform}] {message}" if platform else message, code)


class PlatformNotSupportedException(PlatformException):
    """当平台不被支持时抛出。"""

    def __init__(self, platform: str):
        super().__init__(f"平台 '{platform}' 不被支持", platform, "PLATFORM_NOT_SUPPORTED")


class PlatformConnectionException(PlatformException):
    """当连接平台失败时抛出。"""

    def __init__(self, message: str = "连接平台失败", platform: str = ""):
        super().__init__(message, platform, "PLATFORM_CONNECTION_ERROR")


class PlatformAPIException(PlatformException):
    """当平台 API 调用失败时抛出。"""

    def __init__(self, message: str = "平台 API 调用失败", platform: str = ""):
        super().__init__(message, platform, "PLATFORM_API_ERROR")


class MessageFetchException(PlatformException):
    """当获取消息失败时抛出。"""

    def __init__(self, message: str = "获取消息失败", platform: str = "", group_id: str = ""):
        self.group_id = group_id
        super().__init__(f"{message} (群组: {group_id})" if group_id else message, platform, "MESSAGE_FETCH_ERROR")


class MessageSendException(PlatformException):
    """当发送消息失败时抛出。"""

    def __init__(self, message: str = "发送消息失败", platform: str = "", group_id: str = ""):
        self.group_id = group_id
        super().__init__(f"{message} (群组: {group_id})" if group_id else message, platform, "MESSAGE_SEND_ERROR")


# ============================================================================
# 配置异常
# ============================================================================


class ConfigurationException(DomainException):
    """配置相关错误的基础异常。"""

    def __init__(self, message: str, code: str = "CONFIG_ERROR"):
        super().__init__(message, code)


class InvalidConfigurationException(ConfigurationException):
    """当配置无效时抛出。"""

    def __init__(self, message: str = "无效的配置", key: str = ""):
        self.key = key
        super().__init__(f"{message}: {key}" if key else message, "INVALID_CONFIG")


class MissingConfigurationException(ConfigurationException):
    """当缺少必需配置时抛出。"""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"缺少必需配置: {key}", "MISSING_CONFIG")


# ============================================================================
# 仓储异常
# ============================================================================


class RepositoryException(DomainException):
    """仓储相关错误的基础异常。"""

    def __init__(self, message: str, code: str = "REPOSITORY_ERROR"):
        super().__init__(message, code)


class DataNotFoundException(RepositoryException):
    """当请求的数据未找到时抛出。"""

    def __init__(self, message: str = "数据未找到", entity_type: str = "", entity_id: str = ""):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} 未找到: {entity_id}" if entity_type else message, "DATA_NOT_FOUND")


class DataPersistenceException(RepositoryException):
    """当数据持久化失败时抛出。"""

    def __init__(self, message: str = "数据持久化失败"):
        super().__init__(message, "DATA_PERSISTENCE_ERROR")


# ============================================================================
# 调度异常
# ============================================================================


class SchedulingException(DomainException):
    """调度相关错误的基础异常。"""

    def __init__(self, message: str, code: str = "SCHEDULING_ERROR"):
        super().__init__(message, code)


class TaskAlreadyScheduledException(SchedulingException):
    """当尝试调度已调度的任务时抛出。"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"任务已调度: {task_id}", "TASK_ALREADY_SCHEDULED")


class TaskNotFoundException(SchedulingException):
    """当找不到已调度的任务时抛出。"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"未找到已调度的任务: {task_id}", "TASK_NOT_FOUND")


# ============================================================================
# 验证异常
# ============================================================================


class ValidationException(DomainException):
    """验证错误的基础异常。"""

    def __init__(self, message: str, field: str = "", code: str = "VALIDATION_ERROR"):
        self.field = field
        super().__init__(f"{field}: {message}" if field else message, code)


class InvalidGroupIdException(ValidationException):
    """当群组 ID 无效时抛出。"""

    def __init__(self, group_id: str):
        super().__init__(f"无效的群组 ID: {group_id}", "group_id", "INVALID_GROUP_ID")


class InvalidUserIdException(ValidationException):
    """当用户 ID 无效时抛出。"""

    def __init__(self, user_id: str):
        super().__init__(f"无效的用户 ID: {user_id}", "user_id", "INVALID_USER_ID")


class InvalidMessageException(ValidationException):
    """当消息格式无效时抛出。"""

    def __init__(self, message: str = "无效的消息格式"):
        super().__init__(message, "message", "INVALID_MESSAGE")
