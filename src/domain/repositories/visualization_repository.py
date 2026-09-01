"""
可视化仓储接口 - 领域层
定义活跃度可视化的抽象契约。
"""

from abc import ABC, abstractmethod

from ..models.data_models import ActivityVisualization


class IActivityVisualizer(ABC):
    """活跃度可视化接口 - 领域层抽象"""

    @abstractmethod
    def generate_activity_visualization(
        self, messages: list[dict]
    ) -> ActivityVisualization:
        """从消息列表生成活跃度可视化数据"""
        pass
