"""
Bot实例管理模块
统一管理bot实例的获取、设置和使用
"""

from typing import Optional, Dict, Any
from astrbot.api import logger

class BotManager:
    """Bot实例管理器 - 统一管理所有bot相关操作"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self._bot_instance = None
        self._bot_qq_id = None
        self._context = None
        self._is_initialized = False
    
    def set_context(self, context):
        """设置AstrBot上下文"""
        self._context = context
    
    def set_bot_instance(self, bot_instance):
        """设置bot实例"""
        if bot_instance:
            self._bot_instance = bot_instance
            try:
                logger.info(f"Bot实例已设置: {type(bot_instance).__name__}")
            except ImportError:
                print(f"Bot实例已设置: {type(bot_instance).__name__}")
        else:
            try:
                logger.warning("尝试设置空的bot实例")
            except ImportError:
                print("尝试设置空的bot实例")
    
    def set_bot_qq_id(self, bot_qq_id: str):
        """设置bot QQ号"""
        if bot_qq_id:
            self._bot_qq_id = str(bot_qq_id)
            try:
                logger.info(f"Bot QQ号已设置: {self._bot_qq_id}")
            except ImportError:
                print(f"Bot QQ号已设置: {self._bot_qq_id}")
        else:
            try:
                logger.warning("尝试设置空的bot QQ号")
            except ImportError:
                print("尝试设置空的bot QQ号")
    
    def get_bot_instance(self):
        """获取当前bot实例"""
        return self._bot_instance
    
    def has_bot_instance(self) -> bool:
        """检查是否有可用的bot实例"""
        return self._bot_instance is not None
    
    def has_bot_qq_id(self) -> bool:
        """检查是否有配置的bot QQ号"""
        return self._bot_qq_id is not None
    
    def is_ready_for_auto_analysis(self) -> bool:
        """检查是否准备好进行自动分析"""
        return self.has_bot_instance() and self.has_bot_qq_id()
    
    def is_ready_for_manual_analysis(self) -> bool:
        """检查是否准备好进行手动分析"""
        return self.has_bot_instance()
    
    async def auto_discover_bot_instance(self) -> Optional[Any]:
        """自动发现可用的bot实例"""
        try:
            if not self._context:
                logger.warning("未设置AstrBot上下文，无法自动发现bot实例")
                return None
            
            # 通过platform_manager获取平台实例
            if hasattr(self._context, 'platform_manager') and hasattr(self._context.platform_manager, 'platform_insts'):
                platforms = self._context.platform_manager.platform_insts
                for platform in platforms:
                    # 对于aiocqhttp适配器，bot实例在get_client()方法中
                    if hasattr(platform, 'get_client'):
                        bot_client = platform.get_client()
                        if bot_client:
                            logger.info(f"自动发现bot实例: {type(bot_client).__name__}")
                            self.set_bot_instance(bot_client)
                            return bot_client
                    # 也检查是否直接有bot属性
                    elif hasattr(platform, 'bot') and platform.bot:
                        logger.info(f"自动发现bot实例: {type(platform.bot).__name__}")
                        self.set_bot_instance(platform.bot)
                        return platform.bot
            
            logger.warning("未找到可用的bot实例")
            return None
            
        except Exception as e:
            logger.error(f"自动发现bot实例失败: {e}")
            return None
    
    async def initialize_from_config(self) -> bool:
        """从配置初始化bot管理器"""
        try:
            # 获取配置的bot QQ号
            bot_qq_id = self.config_manager.get_bot_qq_id()
            if bot_qq_id:
                self.set_bot_qq_id(bot_qq_id)
            else:
                logger.warning("配置中未找到bot QQ号")
            
            # 自动发现bot实例
            await self.auto_discover_bot_instance()

            self._is_initialized = True
            
            if self.is_ready_for_auto_analysis():
                logger.info("Bot管理器初始化完成，可进行自动分析")
                return True
            elif self.has_bot_instance():
                logger.info("Bot管理器初始化完成，可进行手动分析")
                return True
            else:
                logger.warning("Bot管理器初始化完成，但功能受限")
                return False
                
        except Exception as e:
            logger.error(f"Bot管理器初始化失败: {e}")
            return False
    
    def get_status_info(self) -> Dict[str, Any]:
        """获取bot管理器状态信息"""
        return {
            "has_bot_instance": self.has_bot_instance(),
            "has_bot_qq_id": self.has_bot_qq_id(),
            "bot_qq_id": self._bot_qq_id,
            "bot_instance_type": type(self._bot_instance).__name__ if self._bot_instance else None,
            "ready_for_auto_analysis": self.is_ready_for_auto_analysis(),
            "ready_for_manual_analysis": self.is_ready_for_manual_analysis(),
            "is_initialized": self._is_initialized
        }
    
    def update_from_event(self, event):
        """从事件更新bot实例（用于手动命令）"""
        if hasattr(event, 'bot') and event.bot:
            self.set_bot_instance(event.bot)
            return True
        return False
    
    def validate_for_message_fetching(self, group_id: str) -> tuple[bool, str]:
        """验证是否可以进行消息获取"""
        if not self.has_bot_instance():
            return False, f"群 {group_id}: 没有可用的bot实例"
        
        if not group_id:
            return False, "无效的群组ID"
        
        return True, "验证通过"
    
    def should_filter_bot_message(self, sender_id: str) -> bool:
        """判断是否应该过滤bot自己的消息"""
        if not self._bot_qq_id:
            return False
        return str(sender_id) == self._bot_qq_id
