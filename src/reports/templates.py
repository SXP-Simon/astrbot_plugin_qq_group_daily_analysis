"""
HTML模板模块
严格按照main-backup中的实现，包含图片报告和PDF报告的不同HTML模板
"""


class HTMLTemplates:
    """HTML模板管理类"""

    @staticmethod
    def get_image_template() -> str:
        """获取图片报告的HTML模板（使用{{ }}占位符）"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>群聊日常分析报告</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Noto Sans SC', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            min-height: 100vh;
            padding: 30px;
            line-height: 1.6;
            color: #1a1a1a;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #4299e1 0%, #667eea 100%);
            color: #ffffff;
            padding: 60px 50px;
            text-align: center;
            border-radius: 30px 30px 0 0;
        }

        .header h1 {
            font-size: 3.2em;
            font-weight: 300;
            margin-bottom: 16px;
            letter-spacing: -1px;
        }

        .header .date {
            font-size: 1.2em;
            opacity: 0.8;
            font-weight: 300;
            letter-spacing: 0.5px;
        }

        .content {
            padding: 40px;
        }

        .topics-grid,
        .users-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 25px;
            align-items: stretch;
        }

        .section {
            margin-bottom: 0;
        }

        .full-width-section {
            grid-column: 1 / -1;
            margin-bottom: 40px;
        }

        .section-title {
            font-size: 1.6em;
            font-weight: 600;
            margin-bottom: 25px;
            color: #4a5568;
            letter-spacing: -0.3px;
            display: flex;
            align-items: center;
            gap: 10px;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 10px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 25px;
            margin-bottom: 40px;
        }

        .stat-card {
            background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
            padding: 40px 30px;
            text-align: center;
            border-radius: 25px;
            border: 1px solid #e2e8f0;
            transition: all 0.3s ease;
        }

        .stat-number {
            font-size: 3.2em;
            font-weight: 300;
            color: #4299e1;
            margin-bottom: 10px;
            display: block;
            letter-spacing: -1px;
        }

        .stat-label {
            font-size: 1em;
            color: #666666;
            font-weight: 400;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .active-period {
            background: linear-gradient(135deg, #4299e1 0%, #667eea 100%);
            color: #ffffff;
            padding: 40px;
            text-align: center;
            margin: 60px 0;
            border-radius: 25px;
            box-shadow: 0 8px 24px rgba(66, 153, 225, 0.3);
        }

        .active-period .time {
            font-size: 3.2em;
            font-weight: 200;
            margin-bottom: 10px;
            letter-spacing: -1px;
        }

        .active-period .label {
            font-size: 1em;
            opacity: 0.8;
            font-weight: 300;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .topic-item {
            background: #ffffff;
            padding: 25px;
            margin-bottom: 0;
            border-radius: 15px;
            border: 1px solid #e5e5e5;
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
            height: 100%;
            box-sizing: border-box;
        }

        .topic-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }

        .topic-number {
            background: linear-gradient(135deg, #3182ce 0%, #2c5282 100%);
            color: #ffffff;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 500;
            margin-right: 16px;
            font-size: 1em;
            box-shadow: 0 4px 12px rgba(49, 130, 206, 0.3);
        }

        .topic-title {
            font-weight: 600;
            color: #2d3748;
            font-size: 1.3em;
            letter-spacing: -0.3px;
        }

        .topic-contributors {
            color: #666666;
            font-size: 1em;
            margin-bottom: 16px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .topic-detail {
            color: #333333;
            line-height: 1.6;
            font-size: 1em;
            font-weight: 300;
        }

        .user-title {
            background: #ffffff;
            padding: 20px;
            margin-bottom: 0;
            border-radius: 15px;
            border: 1px solid #e5e5e5;
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            transition: all 0.3s ease;
            min-height: 100px;
            height: 100%;
            box-sizing: border-box;
        }

        .user-info {
            display: flex;
            align-items: center;
            flex: 1;
        }

        .user-avatar {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            margin-right: 20px;
            border: 2px solid #f0f0f0;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .user-avatar-placeholder {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #f0f0f0 0%, #e2e8f0 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 20px;
            font-size: 1.2em;
            color: #999999;
            border: 2px solid #e5e5e5;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .user-details {
            flex: 1;
        }

        .user-name {
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 15px;
            font-size: 1.2em;
            letter-spacing: -0.2px;
        }

        .user-badges {
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: nowrap;
            overflow-x: auto;
        }

        .user-title-badge,
        .user-mbti {
            white-space: nowrap;
            display: inline-flex;
            align-items: center;
        }

        .user-title-badge {
            background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%);
            color: #ffffff;
            padding: 8px 20px;
            border-radius: 25px;
            font-size: 0.9em;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            box-shadow: 0 2px 8px rgba(66, 153, 225, 0.3);
        }

        .user-mbti {
            background: linear-gradient(135deg, #667eea 0%, #5a67d8 100%);
            color: #ffffff;
            padding: 8px 15px;
            border-radius: 20px;
            font-weight: 500;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        }

        .user-reason {
            color: #666666;
            font-size: 1em;
            text-align: right;
            line-height: 1.4;
            font-weight: 300;
            margin-left: 20px;
            flex: 1;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }

        .quote-item {
            background: #ffffff;
            padding: 16px;
            margin-bottom: 16px;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            position: relative;
            transition: all 0.3s ease;
        }

        .quote-content {
            font-size: 1.1em;
            color: #2d3748;
            font-weight: 500;
            line-height: 1.6;
            margin-bottom: 12px;
            font-style: italic;
            letter-spacing: 0.2px;
        }

        .quote-author {
            font-size: 0.9em;
            color: #4299e1;
            font-weight: 600;
            margin-bottom: 8px;
            text-align: right;
        }

        .quote-reason {
            font-size: 0.8em;
            color: #666666;
            font-style: normal;
            background: rgba(66, 153, 225, 0.1);
            padding: 8px 12px;
            border-radius: 12px;
            border-left: 3px solid #4299e1;
        }

        .footer {
            background: linear-gradient(135deg, #3182ce 0%, #2c5282 100%);
            color: #ffffff;
            text-align: center;
            padding: 40px;
            font-size: 1em;
            font-weight: 300;
            letter-spacing: 0.5px;
            opacity: 0.9;
        }

        /* 活跃度可视化样式 - 重新设计 */
        .activity-section {
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            padding: 50px;
            border-radius: 25px;
            margin: 50px 0;
            border: 1px solid #e2e8f0;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        }

        .activity-chart-container {
            background: #ffffff;
            padding: 40px;
            border-radius: 20px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
        }

        .chart-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #f0f2f5;
        }

        .chart-title {
            font-size: 1.6em;
            font-weight: 600;
            color: #2d3748;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .chart-subtitle {
            color: #7f8c8d;
            font-size: 1.1em;
            font-weight: 400;
        }

        .hour-bar-container {
            display: flex;
            align-items: center;
            margin: 12px 0;
            height: 25px;
            transition: all 0.2s ease;
        }

        .hour-label {
            width: 65px;
            text-align: left;
            color: #4a5568;
            font-size: 15px;
            font-weight: 500;
            flex-shrink: 0;
        }

        .bar-wrapper {
            display: flex;
            align-items: center;
            flex-grow: 1;
            gap: 15px;
            min-width: 0;
        }

        .bar {
            height: 12px;
            background: linear-gradient(90deg, #4299e1 0%, #667eea 100%);
            border-radius: 8px;
            transition: all 0.3s ease-out;
            display: flex;
            justify-content: flex-end;
            align-items: center;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(66, 153, 225, 0.2);
        }

        .hourly-value-outside {
            color: #4a5568;
            font-size: 14px;
            font-weight: 600;
            flex-shrink: 0;
            min-width: 35px;
            text-align: right;
        }

        .hourly-value-inside {
            color: white;
            font-size: 13px;
            padding: 0 10px;
            font-weight: 600;
            white-space: nowrap;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
        }

        @media (min-width: 1400px) {
            .container {
                max-width: 1600px;
            }

            .topics-grid {
                grid-template-columns: repeat(3, 1fr);
            }

            .users-grid {
                grid-template-columns: repeat(3, 1fr);
            }
        }

        @media (max-width: 768px) {
            body {
                padding: 15px;
            }

            .container {
                margin: 0;
                max-width: 100%;
            }

            .header {
                padding: 30px 25px;
            }

            .header h1 {
                font-size: 2.2em;
            }

            .content {
                padding: 25px;
            }

            .topics-grid {
                grid-template-columns: 1fr;
            }

            .users-grid {
                grid-template-columns: 1fr;
            }

            .stats-grid {
                grid-template-columns: 1fr 1fr;
                gap: 15px;
            }

            .stat-card {
                padding: 25px 20px;
            }

            .topic-item {
                padding: 25px;
            }

            .user-title {
                flex-direction: column;
                align-items: flex-start;
                gap: 15px;
                padding: 20px;
                min-height: auto;
            }

            .user-info {
                width: 100%;
            }

            .user-reason {
                text-align: left;
                max-width: none;
                margin-left: 0;
                margin-top: 10px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 群聊日常分析报告</h1>
            <div class="date">{{ current_date }}</div>
        </div>
        <div class="content">
            <div class="section full-width-section">
                <h2 class="section-title">📈 基础统计</h2>
                <div class="stats-grid">
                    <div class="stat-card"><div class="stat-number">{{ message_count }}</div><div class="stat-label">消息总数</div></div>
                    <div class="stat-card"><div class="stat-number">{{ participant_count }}</div><div class="stat-label">参与人数</div></div>
                    <div class="stat-card"><div class="stat-number">{{ total_characters }}</div><div class="stat-label">总字符数</div></div>
                    <div class="stat-card"><div class="stat-number">{{ emoji_count }}</div><div class="stat-label">表情数量</div></div>
                </div>
                <div class="active-period">
                    <div class="time">{{ most_active_period }}</div>
                    <div class="label">最活跃时段</div>
                </div>
            </div>

            <!-- 活跃度可视化部分 - 重新设计 -->
            <div class="activity-chart-container">
                <div class="chart-header">
                    <div>
                        <div class="chart-title">⏱️ 24小时活跃度分布</div>
                    </div>
                </div>
                {{ hourly_chart_html | safe }}
            </div>
            <div class="section">
                <h2 class="section-title">💬 热门话题</h2>
                <div class="topics-grid">{{ topics_html | safe }}</div>
            </div>
            <div class="section">
                <h2 class="section-title">🏆 群友称号</h2>
                <div class="users-grid">{{ titles_html | safe }}</div>
            </div>
            <div class="section">
                <h2 class="section-title">💬 群圣经</h2>
                {{ quotes_html | safe }}
            </div>
        </div>
        <div class="footer">
            由 AstrBot QQ群日常分析插件 生成 | {{ current_datetime }} | SXP-Simon/astrbot-qq-group-daily-analysis<br>
            <small style="opacity: 0.8; font-size: 0.9em;">🤖 AI分析消耗：{{ total_tokens }} tokens (输入: {{ prompt_tokens }}, 输出: {{ completion_tokens }})</small>
        </div>
    </div>
</body>
</html>"""

    @staticmethod
    def get_pdf_template() -> str:
        """获取PDF报告的HTML模板（使用{}占位符）"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>群聊日常分析报告</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
            background: #ffffff;
            color: #1a1a1a;
            line-height: 1.6;
            font-size: 14px;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            background: linear-gradient(135deg, #4299e1 0%, #667eea 100%);
            color: #ffffff;
            padding: 30px;
            text-align: center;
            border-radius: 12px;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .header .date {
            font-size: 16px;
            opacity: 0.9;
        }

        .section {
            margin-bottom: 40px;
            page-break-inside: avoid;
        }

        .section-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #4a5568;
            border-bottom: 2px solid #4299e1;
            padding-bottom: 8px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: #f8f9ff;
            padding: 20px;
            text-align: center;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }

        .stat-number {
            font-size: 24px;
            font-weight: 600;
            color: #4299e1;
            margin-bottom: 5px;
        }

        .stat-label {
            font-size: 12px;
            color: #666666;
            text-transform: uppercase;
        }

        .active-period {
            background: linear-gradient(135deg, #4299e1 0%, #667eea 100%);
            color: #ffffff;
            padding: 25px;
            text-align: center;
            margin: 30px 0;
            border-radius: 8px;
        }

        .active-period .time {
            font-size: 28px;
            font-weight: 300;
            margin-bottom: 5px;
        }

        .active-period .label {
            font-size: 14px;
            opacity: 0.9;
        }

        .topic-item {
            background: #ffffff;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            page-break-inside: avoid;
        }

        .topic-header {
            display: flex;
            align-items: center;
            margin-bottom: 12px;
        }

        .topic-number {
            background: #4299e1;
            color: #ffffff;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            margin-right: 12px;
            font-size: 12px;
        }

        .topic-title {
            font-weight: 600;
            color: #2d3748;
            font-size: 16px;
        }

        .topic-contributors {
            color: #666666;
            font-size: 12px;
            margin-bottom: 10px;
        }

        .topic-detail {
            color: #333333;
            line-height: 1.6;
            font-size: 14px;
        }

        .user-title {
            background: #ffffff;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            page-break-inside: avoid;
        }

        .user-info {
            display: flex;
            align-items: center;
            flex: 1;
        }

        .user-details {
            flex: 1;
        }

        .user-name {
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 8px;
            font-size: 16px;
        }

        .user-badges {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }

        .user-title-badge {
            background: #4299e1;
            color: #ffffff;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }

        .user-mbti {
            background: #667eea;
            color: #ffffff;
            padding: 4px 8px;
            border-radius: 8px;
            font-weight: 500;
            font-size: 12px;
        }

        .user-reason {
            color: #666666;
            font-size: 12px;
            max-width: 200px;
            text-align: right;
            line-height: 1.4;
        }

        .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            margin-right: 15px;
            border: 2px solid #e2e8f0;
            object-fit: cover;
            flex-shrink: 0;
        }

        .user-avatar-placeholder {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: #f0f0f0;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 15px;
            font-size: 18px;
            color: #666666;
            flex-shrink: 0;
        }

        .quote-item {
            background: #faf5ff;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            page-break-inside: avoid;
        }

        .quote-content {
            font-size: 16px;
            color: #2d3748;
            font-weight: 500;
            line-height: 1.6;
            margin-bottom: 10px;
            font-style: italic;
        }

        .quote-author {
            font-size: 14px;
            color: #4299e1;
            font-weight: 600;
            margin-bottom: 8px;
            text-align: right;
        }

        .quote-reason {
            font-size: 12px;
            color: #666666;
            background: rgba(66, 153, 225, 0.1);
            padding: 8px 12px;
            border-radius: 6px;
            border-left: 3px solid #4299e1;
        }

        .footer {
            background: #f8f9ff;
            color: #666666;
            text-align: center;
            padding: 20px;
            font-size: 12px;
            border-radius: 8px;
            margin-top: 40px;
        }

        /* PDF活跃度可视化样式 - 集成版本 */
        .activity-chart-container {
            background: #f8f9ff;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            margin-top: 20px;
            page-break-inside: avoid;
        }

        .chart-header {
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 1px solid #e2e8f0;
        }

        .chart-title {
            font-size: 16px;
            font-weight: 600;
            color: #2d3748;
        }

        .hour-bar-container {
            display: flex;
            align-items: center;
            margin: 6px 0;
            height: 16px;
        }

        .hour-label {
            width: 45px;
            text-align: left;
            color: #4a5568;
            font-size: 11px;
            font-weight: 500;
            flex-shrink: 0;
        }

        .bar-wrapper {
            display: flex;
            align-items: center;
            flex-grow: 1;
            gap: 8px;
            min-width: 0;
        }

        .bar {
            height: 6px;
            background-color: #4299e1;
            border-radius: 3px;
            display: flex;
            justify-content: flex-end;
            align-items: center;
            overflow: hidden;
        }

        .hourly-value-outside {
            color: #4a5568;
            font-size: 10px;
            font-weight: 600;
            flex-shrink: 0;
            min-width: 25px;
            text-align: right;
        }

        .hourly-value-inside {
            color: white;
            font-size: 9px;
            padding: 0 4px;
            font-weight: 600;
            white-space: nowrap;
        }

        @media print {
            body {
                font-size: 12px;
            }

            .container {
                padding: 10px;
            }

            .header {
                padding: 20px;
            }

            .section {
                margin-bottom: 30px;
            }

            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>

<body>
    <div class="container">
        <div class="header">
            <h1>📊 群聊日常分析报告</h1>
            <div class="date">{current_date}</div>
        </div>
        <div class="section">
            <h2 class="section-title">📈 基础统计</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">{message_count}</div>
                    <div class="stat-label">消息总数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{participant_count}</div>
                    <div class="stat-label">参与人数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{total_characters}</div>
                    <div class="stat-label">总字符数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{emoji_count}</div>
                    <div class="stat-label">表情数量</div>
                </div>
            </div>
            <div class="active-period">
                <div class="time">{most_active_period}</div>
                <div class="label">最活跃时段</div>
            </div>
            <!-- 活跃度可视化部分 - 集成到基础统计 -->
            <div class="activity-chart-container">
                <div class="chart-header">
                    <div class="chart-title">⏱️ 活跃度分布</div>
                </div>
                {hourly_chart_html}
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">💬 热门话题</h2>
            {topics_html}
        </div>
        <div class="section">
            <h2 class="section-title">🏆 群友称号</h2>
            {titles_html}
        </div>
        <div class="section">
            <h2 class="section-title">💬 群圣经</h2>
            {quotes_html}
        </div>
        <div class="footer">
            由 AstrBot QQ群日常分析插件 生成 | {current_datetime} | SXP-Simon/astrbot-qq-group-daily-analysis<br>
            <small style="opacity: 0.8; font-size: 0.9em;">🤖 AI分析消耗：{total_tokens} tokens (输入: {prompt_tokens}, 输出:
                {completion_tokens})</small>
        </div>
    </div>
</body>

</html>"""
