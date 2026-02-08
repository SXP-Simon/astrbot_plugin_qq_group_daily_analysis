"""
Analysis Orchestrator - Application layer coordinator

This orchestrator bridges the new DDD architecture with the existing
analysis logic, providing a gradual migration path.

Architecture Decision:
- The orchestrator uses PlatformAdapter for message fetching (new DDD way)
- But delegates to existing analyzers for LLM analysis (preserving working code)
- MessageConverter provides bidirectional conversion for compatibility
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from astrbot.api import logger

from ..domain.value_objects.unified_message import UnifiedMessage
from ..domain.value_objects.platform_capabilities import PlatformCapabilities
from ..infrastructure.platform import PlatformAdapter, PlatformAdapterFactory
from .message_converter import MessageConverter


@dataclass
class AnalysisConfig:
    """Configuration for analysis operation"""
    days: int = 1
    max_messages: int = 1000
    min_messages_threshold: int = 10
    output_format: str = "image"


class AnalysisOrchestrator:
    """
    Analysis orchestrator - coordinates the analysis workflow.
    
    Responsibilities:
    1. Use PlatformAdapter to fetch messages (DDD approach)
    2. Convert messages for compatibility with existing analyzers
    3. Coordinate analysis flow
    4. Provide platform capability checks
    
    This class serves as the bridge between:
    - New DDD infrastructure (PlatformAdapter, UnifiedMessage)
    - Existing analysis logic (MessageHandler, LLMAnalyzer, etc.)
    """

    def __init__(
        self,
        adapter: PlatformAdapter,
        config: AnalysisConfig = None,
    ):
        """
        Initialize the orchestrator.
        
        Args:
            adapter: Platform adapter for message operations
            config: Analysis configuration
        """
        self.adapter = adapter
        self.config = config or AnalysisConfig()

    @classmethod
    def create_for_platform(
        cls,
        platform_name: str,
        bot_instance: Any,
        config: dict = None,
        analysis_config: AnalysisConfig = None,
    ) -> Optional["AnalysisOrchestrator"]:
        """
        Factory method to create orchestrator for a specific platform.
        
        Args:
            platform_name: Platform name (e.g., "aiocqhttp", "telegram")
            bot_instance: Bot instance from AstrBot
            config: Platform-specific config
            analysis_config: Analysis configuration
            
        Returns:
            AnalysisOrchestrator or None if platform not supported
        """
        adapter = PlatformAdapterFactory.create(platform_name, bot_instance, config)
        if adapter is None:
            logger.warning(f"Platform '{platform_name}' not supported for analysis")
            return None
        
        return cls(adapter, analysis_config)

    def get_capabilities(self) -> PlatformCapabilities:
        """Get platform capabilities."""
        return self.adapter.get_capabilities()

    def can_analyze(self) -> bool:
        """Check if the platform supports analysis."""
        return self.adapter.get_capabilities().can_analyze()

    def can_send_report(self, format: str = "image") -> bool:
        """Check if the platform can send reports in the specified format."""
        return self.adapter.get_capabilities().can_send_report(format)

    async def fetch_messages(
        self,
        group_id: str,
        days: int = None,
        max_count: int = None,
    ) -> List[UnifiedMessage]:
        """
        Fetch messages using the platform adapter.
        
        Args:
            group_id: Group ID to fetch messages from
            days: Number of days (defaults to config)
            max_count: Maximum message count (defaults to config)
            
        Returns:
            List of UnifiedMessage
        """
        days = days or self.config.days
        max_count = max_count or self.config.max_messages
        
        # Apply platform capability limits
        caps = self.adapter.get_capabilities()
        effective_days = caps.get_effective_days(days)
        effective_count = caps.get_effective_count(max_count)
        
        if effective_days < days:
            logger.info(
                f"Platform limits: requested {days} days, "
                f"using {effective_days} days"
            )
        
        return await self.adapter.fetch_messages(
            group_id=group_id,
            days=effective_days,
            max_count=effective_count,
        )

    async def fetch_messages_as_raw(
        self,
        group_id: str,
        days: int = None,
        max_count: int = None,
    ) -> List[dict]:
        """
        Fetch messages and convert to raw dict format.
        
        This provides backward compatibility with existing analyzers
        that expect raw dict messages.
        
        Args:
            group_id: Group ID to fetch messages from
            days: Number of days
            max_count: Maximum message count
            
        Returns:
            List of raw message dicts (OneBot format)
        """
        unified_messages = await self.fetch_messages(group_id, days, max_count)
        return MessageConverter.batch_to_onebot(unified_messages)

    async def get_group_info(self, group_id: str):
        """Get group information."""
        return await self.adapter.get_group_info(group_id)

    async def get_member_avatars(
        self,
        user_ids: List[str],
        size: int = 100,
    ) -> Dict[str, Optional[str]]:
        """
        Batch get user avatar URLs.
        
        Args:
            user_ids: List of user IDs
            size: Avatar size
            
        Returns:
            Dict mapping user_id to avatar URL (or None)
        """
        return await self.adapter.batch_get_avatar_urls(user_ids, size)

    async def send_text(self, group_id: str, text: str) -> bool:
        """Send text message to group."""
        return await self.adapter.send_text(group_id, text)

    async def send_image(
        self,
        group_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """Send image to group."""
        return await self.adapter.send_image(group_id, image_path, caption)

    async def send_file(
        self,
        group_id: str,
        file_path: str,
        filename: str = None,
    ) -> bool:
        """Send file to group."""
        return await self.adapter.send_file(group_id, file_path, filename)

    def validate_message_count(self, messages: List[UnifiedMessage]) -> bool:
        """
        Check if message count meets minimum threshold.
        
        Args:
            messages: List of messages
            
        Returns:
            True if count is sufficient
        """
        return len(messages) >= self.config.min_messages_threshold

    def get_analysis_text(self, messages: List[UnifiedMessage]) -> str:
        """
        Convert messages to analysis text format for LLM.
        
        Args:
            messages: List of UnifiedMessage
            
        Returns:
            Formatted text for LLM analysis
        """
        return MessageConverter.unified_to_analysis_text(messages)
