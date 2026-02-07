import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

# 模拟环境
sys.modules['astrbot'] = MagicMock()
sys.modules['astrbot.api'] = MagicMock()

async def verify_history():
    print("开始验证 HistoryManager...")
    
    # 模拟 Star 实例
    mock_star = MagicMock()
    mock_star.put_kv_data = AsyncMock()
    mock_star.get_kv_data = AsyncMock()
    
    # 导入 HistoryManager (使用相对路径或动态导入)
    from src.core.history_manager import HistoryManager
    
    hm = HistoryManager(mock_star)
    
    # 1. 测试保存分析
    group_id = "123456"
    mock_stats = MagicMock()
    mock_stats.message_count = 100
    mock_stats.participant_count = 10
    
    analysis_result = {
        "statistics": mock_stats,
        "topics": [],
        "user_titles": []
    }
    
    print(f"测试保存群 {group_id} 的分析摘要 (带时间槽)...")
    await hm.save_analysis(group_id, analysis_result, "2026-02-08", "12-00")
    
    # 验证 put_kv_data 被调用，且 key 正确
    expected_key = f"analysis_{group_id}_2026-02-08_12-00"
    mock_star.put_kv_data.assert_called_once()
    actual_key = mock_star.put_kv_data.call_args[0][0]
    actual_data = mock_star.put_kv_data.call_args[0][1]
    
    assert actual_key == expected_key
    assert actual_data["message_count"] == 100
    print(f"✅ 保存验证成功: Key={actual_key}")
    
    # 2. 测试检查历史 (不同时间点)
    mock_star.get_kv_data.side_effect = lambda type, pid, key, default: {"message_count": 100} if "12-00" in key else None
    
    has_history_12 = await hm.has_history(group_id, "2026-02-08", "12-00")
    assert has_history_12 is True
    print(f"✅ 12:00 历史检查成功")
    
    has_history_13 = await hm.has_history(group_id, "2026-02-08", "13-00")
    assert has_history_13 is False
    print(f"✅ 13:00 (无历史) 检查成功")

if __name__ == "__main__":
    asyncio.run(verify_history())
