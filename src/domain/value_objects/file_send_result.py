"""文件发送结果值对象。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FileSendResult:
    """统一描述文件发送结果，支持“不确定超时”状态。"""

    success: bool
    status: str
    platform: str = ""
    message_id: str | None = None
    error: str = ""

    @classmethod
    def sent(
        cls,
        platform: str = "",
        message_id: str | None = None,
    ) -> "FileSendResult":
        return cls(success=True, status="sent", platform=platform, message_id=message_id)

    @classmethod
    def assumed_sent(cls, platform: str = "", error: str = "") -> "FileSendResult":
        return cls(success=True, status="assumed_sent", platform=platform, error=error)

    @classmethod
    def skipped_duplicate(cls, platform: str = "") -> "FileSendResult":
        return cls(success=True, status="skipped_duplicate", platform=platform)

    @classmethod
    def timeout_unknown(cls, platform: str = "", error: str = "") -> "FileSendResult":
        return cls(success=False, status="timeout_unknown", platform=platform, error=error)

    @classmethod
    def failed(cls, platform: str = "", error: str = "") -> "FileSendResult":
        return cls(success=False, status="failed", platform=platform, error=error)
