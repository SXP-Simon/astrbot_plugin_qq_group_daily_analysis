"""
Domain Exceptions - Custom exceptions for the domain layer

This module contains all domain-specific exceptions used throughout
the plugin. These exceptions are platform-agnostic and represent
business logic errors.
"""


class DomainException(Exception):
    """Base exception for all domain errors."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


# ============================================================================
# Analysis Exceptions
# ============================================================================


class AnalysisException(DomainException):
    """Base exception for analysis-related errors."""

    def __init__(self, message: str, code: str = "ANALYSIS_ERROR"):
        super().__init__(message, code)


class InsufficientDataException(AnalysisException):
    """Raised when there is not enough data to perform analysis."""

    def __init__(self, message: str = "Insufficient data for analysis"):
        super().__init__(message, "INSUFFICIENT_DATA")


class AnalysisTimeoutException(AnalysisException):
    """Raised when analysis takes too long."""

    def __init__(self, message: str = "Analysis timed out"):
        super().__init__(message, "ANALYSIS_TIMEOUT")


class LLMException(AnalysisException):
    """Raised when LLM API call fails."""

    def __init__(self, message: str = "LLM API call failed", provider: str = ""):
        self.provider = provider
        super().__init__(f"{message} (provider: {provider})" if provider else message, "LLM_ERROR")


class LLMRateLimitException(LLMException):
    """Raised when LLM API rate limit is exceeded."""

    def __init__(self, message: str = "LLM rate limit exceeded", provider: str = ""):
        super().__init__(message, provider)
        self.code = "LLM_RATE_LIMIT"


class LLMQuotaExceededException(LLMException):
    """Raised when LLM API quota is exceeded."""

    def __init__(self, message: str = "LLM quota exceeded", provider: str = ""):
        super().__init__(message, provider)
        self.code = "LLM_QUOTA_EXCEEDED"


# ============================================================================
# Platform Exceptions
# ============================================================================


class PlatformException(DomainException):
    """Base exception for platform-related errors."""

    def __init__(self, message: str, platform: str = "", code: str = "PLATFORM_ERROR"):
        self.platform = platform
        super().__init__(f"[{platform}] {message}" if platform else message, code)


class PlatformNotSupportedException(PlatformException):
    """Raised when a platform is not supported."""

    def __init__(self, platform: str):
        super().__init__(f"Platform '{platform}' is not supported", platform, "PLATFORM_NOT_SUPPORTED")


class PlatformConnectionException(PlatformException):
    """Raised when connection to platform fails."""

    def __init__(self, message: str = "Failed to connect to platform", platform: str = ""):
        super().__init__(message, platform, "PLATFORM_CONNECTION_ERROR")


class PlatformAPIException(PlatformException):
    """Raised when platform API call fails."""

    def __init__(self, message: str = "Platform API call failed", platform: str = ""):
        super().__init__(message, platform, "PLATFORM_API_ERROR")


class MessageFetchException(PlatformException):
    """Raised when fetching messages fails."""

    def __init__(self, message: str = "Failed to fetch messages", platform: str = "", group_id: str = ""):
        self.group_id = group_id
        super().__init__(f"{message} (group: {group_id})" if group_id else message, platform, "MESSAGE_FETCH_ERROR")


class MessageSendException(PlatformException):
    """Raised when sending a message fails."""

    def __init__(self, message: str = "Failed to send message", platform: str = "", group_id: str = ""):
        self.group_id = group_id
        super().__init__(f"{message} (group: {group_id})" if group_id else message, platform, "MESSAGE_SEND_ERROR")


# ============================================================================
# Configuration Exceptions
# ============================================================================


class ConfigurationException(DomainException):
    """Base exception for configuration-related errors."""

    def __init__(self, message: str, code: str = "CONFIG_ERROR"):
        super().__init__(message, code)


class InvalidConfigurationException(ConfigurationException):
    """Raised when configuration is invalid."""

    def __init__(self, message: str = "Invalid configuration", key: str = ""):
        self.key = key
        super().__init__(f"{message}: {key}" if key else message, "INVALID_CONFIG")


class MissingConfigurationException(ConfigurationException):
    """Raised when required configuration is missing."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"Missing required configuration: {key}", "MISSING_CONFIG")


# ============================================================================
# Repository Exceptions
# ============================================================================


class RepositoryException(DomainException):
    """Base exception for repository-related errors."""

    def __init__(self, message: str, code: str = "REPOSITORY_ERROR"):
        super().__init__(message, code)


class DataNotFoundException(RepositoryException):
    """Raised when requested data is not found."""

    def __init__(self, message: str = "Data not found", entity_type: str = "", entity_id: str = ""):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} not found: {entity_id}" if entity_type else message, "DATA_NOT_FOUND")


class DataPersistenceException(RepositoryException):
    """Raised when data persistence fails."""

    def __init__(self, message: str = "Failed to persist data"):
        super().__init__(message, "DATA_PERSISTENCE_ERROR")


# ============================================================================
# Scheduling Exceptions
# ============================================================================


class SchedulingException(DomainException):
    """Base exception for scheduling-related errors."""

    def __init__(self, message: str, code: str = "SCHEDULING_ERROR"):
        super().__init__(message, code)


class TaskAlreadyScheduledException(SchedulingException):
    """Raised when trying to schedule an already scheduled task."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task already scheduled: {task_id}", "TASK_ALREADY_SCHEDULED")


class TaskNotFoundException(SchedulingException):
    """Raised when a scheduled task is not found."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Scheduled task not found: {task_id}", "TASK_NOT_FOUND")


# ============================================================================
# Validation Exceptions
# ============================================================================


class ValidationException(DomainException):
    """Base exception for validation errors."""

    def __init__(self, message: str, field: str = "", code: str = "VALIDATION_ERROR"):
        self.field = field
        super().__init__(f"{field}: {message}" if field else message, code)


class InvalidGroupIdException(ValidationException):
    """Raised when group ID is invalid."""

    def __init__(self, group_id: str):
        super().__init__(f"Invalid group ID: {group_id}", "group_id", "INVALID_GROUP_ID")


class InvalidUserIdException(ValidationException):
    """Raised when user ID is invalid."""

    def __init__(self, user_id: str):
        super().__init__(f"Invalid user ID: {user_id}", "user_id", "INVALID_USER_ID")


class InvalidMessageException(ValidationException):
    """Raised when message format is invalid."""

    def __init__(self, message: str = "Invalid message format"):
        super().__init__(message, "message", "INVALID_MESSAGE")
