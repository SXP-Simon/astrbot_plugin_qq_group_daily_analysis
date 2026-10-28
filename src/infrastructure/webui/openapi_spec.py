"""AstrBot QQ群聊分析插件 Web API 的 OpenAPI 3.1 规范提供器。

本模块构建并提供控制台所需的全量 REST 与 SSE 端点的 OpenAPI 3.1 契约定义。
"""

from __future__ import annotations

from typing import Any


def generate_openapi_spec() -> dict[str, Any]:
    """生成插件 Web API 的 OpenAPI 3.1 契约规范字典。

    Returns:
        dict[str, Any]: 完整的 OpenAPI 3.1 契约规范字典对象。
    """
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "AstrBot QQ Group Daily Analysis Web API",
            "version": "5.6.4",
            "description": "REST API and data contract specification for AstrBot QQ Group Daily Analysis Dashboard",
        },
        "paths": {
            "/config": {
                "get": {
                    "summary": "读取插件配置、表单定义和内容版本",
                    "operationId": "getPluginConfig",
                    "responses": {
                        "200": {
                            "description": "版本对应原始配置；表单中的默认方案可能经过补齐",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"const": "ok"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "config": {
                                                        "type": "object",
                                                        "additionalProperties": True,
                                                    },
                                                    "schema": {
                                                        "type": "object",
                                                        "additionalProperties": True,
                                                    },
                                                    "revision": {
                                                        "type": "string",
                                                        "pattern": "^[0-9a-f]{64}$",
                                                    },
                                                },
                                                "required": [
                                                    "config",
                                                    "schema",
                                                    "revision",
                                                ],
                                            },
                                        },
                                        "required": ["status", "data"],
                                    }
                                }
                            },
                        },
                        "500": {"description": "读取配置失败"},
                    },
                },
                "post": {
                    "summary": "保存配置，带版本时拒绝覆盖过期快照",
                    "operationId": "savePluginConfig",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "config": {
                                            "type": "object",
                                            "additionalProperties": True,
                                        },
                                        "revision": {
                                            "type": "string",
                                            "pattern": "^[0-9a-f]{64}$",
                                            "description": "可选，兼容旧调用方；WebUI 应传入最近读取或保存成功的版本",
                                        },
                                    },
                                    "required": ["config"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "配置保存成功，返回新版本供后续保存使用",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"const": "ok"},
                                            "message": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "additionalProperties": True,
                                            },
                                            "revision": {
                                                "type": "string",
                                                "pattern": "^[0-9a-f]{64}$",
                                            },
                                        },
                                        "required": ["status", "data", "revision"],
                                    }
                                }
                            },
                        },
                        "400": {"description": "配置或版本格式无效"},
                        "409": {
                            "description": "配置已被其他页面或管理界面修改，须重新读取后保存"
                        },
                        "500": {"description": "配置保存失败"},
                    },
                },
            },
            "/config/test-t2i": {
                "post": {
                    "summary": "按当前渲染方案测试 AstrBot 或自定义 T2I，不生成分析报告",
                    "operationId": "testT2i",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/T2iProbeRequest"
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "经校验的图片与耗时，不保存配置或报告",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string", "const": "ok"},
                                            "data": {
                                                "$ref": "#/components/schemas/T2iProbe"
                                            },
                                        },
                                        "required": ["status", "data"],
                                    }
                                }
                            },
                        },
                        "400": {"description": "服务配置无效"},
                        "502": {"description": "服务连接、鉴权、超时或图片校验失败"},
                        "503": {"description": "AstrBot 渲染接口尚未就绪"},
                    },
                },
            },
            "/config/test-template-cdn": {
                "post": {
                    "summary": "从插件服务器通过 HEAD 检查 GitHub 和 npm 资源链接",
                    "operationId": "testTemplateCdn",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/TemplateCdnProbeRequest"
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "仅返回 HEAD 可访问性检测结果，不下载正文；所有返回的 checks 均通过时 usable 才为 true",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "$ref": "#/components/schemas/TemplateCdnProbe"
                                            },
                                        },
                                        "required": ["status", "data"],
                                    }
                                }
                            },
                        },
                        "400": {"description": "Invalid CDN root address"},
                        "500": {"description": "Unexpected probe error"},
                    },
                },
            },
            "/tasks/active": {
                "get": {
                    "summary": "Get active running analysis tasks",
                    "operationId": "getActiveTasks",
                    "responses": {
                        "200": {
                            "description": "Active tasks list",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "type": "array",
                                                "items": {
                                                    "$ref": "#/components/schemas/ActiveTask"
                                                },
                                            },
                                        },
                                        "required": ["status", "data"],
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/tasks/cancel": {
                "post": {
                    "summary": "Cancel an active analysis task",
                    "operationId": "cancelTask",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"task_id": {"type": "string"}},
                                    "required": ["task_id"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Cancellation result",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/tasks/trigger": {
                "post": {
                    "summary": "Trigger an analysis task manually",
                    "operationId": "triggerTask",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "group_id": {"type": "string"},
                                        "group_name": {"type": "string"},
                                        "platform": {"type": "string"},
                                        "trigger_type": {"type": "string"},
                                        "template_id": {"type": "string"},
                                    },
                                    "required": ["group_id"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Trigger task result",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "task_id": {"type": "string"},
                                            "message": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/tasks/{trace_id}/resume": {
                "post": {
                    "summary": "Resume an analysis task from checkpoint",
                    "operationId": "resumeTask",
                    "parameters": [
                        {
                            "name": "trace_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Resume result",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "task_id": {"type": "string"},
                                            "message": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/traces": {
                "get": {
                    "summary": "List execution traces with filters",
                    "operationId": "listTraces",
                    "parameters": [
                        {
                            "name": "group_id",
                            "in": "query",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "status",
                            "in": "query",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "trigger_type",
                            "in": "query",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "default": 20},
                        },
                        {
                            "name": "offset",
                            "in": "query",
                            "schema": {"type": "integer", "default": 0},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "List of traces",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "items": {
                                                        "type": "array",
                                                        "items": {
                                                            "$ref": "#/components/schemas/TraceRecord"
                                                        },
                                                    },
                                                    "total": {"type": "integer"},
                                                },
                                                "required": ["items", "total"],
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/traces/{trace_id}": {
                "get": {
                    "summary": "Get full trace details with spans and metrics",
                    "operationId": "getTraceDetail",
                    "parameters": [
                        {
                            "name": "trace_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Trace details",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "$ref": "#/components/schemas/TraceRecord"
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/metrics/summary": {
                "get": {
                    "summary": "Get KPI and token metrics summary",
                    "operationId": "getMetricsSummary",
                    "responses": {
                        "200": {
                            "description": "Metrics summary",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "$ref": "#/components/schemas/MetricsSummary"
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/metrics/trends": {
                "get": {
                    "summary": "Get time-series trends with hour/day granularity",
                    "operationId": "getAnalyticsTrends",
                    "parameters": [
                        {
                            "name": "granularity",
                            "in": "query",
                            "schema": {
                                "type": "string",
                                "enum": ["day", "hour"],
                                "default": "day",
                            },
                        },
                        {
                            "name": "range_count",
                            "in": "query",
                            "schema": {"type": "integer", "default": 7},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Trends data points",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "$ref": "#/components/schemas/AnalyticsTrendsResponse"
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/groups": {
                "get": {
                    "summary": "Get distinct groups list",
                    "operationId": "getDistinctGroups",
                    "responses": {
                        "200": {
                            "description": "历史群聊的标识、名称和平台实例",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "type": "array",
                                                "items": {
                                                    "$ref": "#/components/schemas/GroupItem"
                                                },
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/platforms": {
                "get": {
                    "summary": "Get connected bot platforms",
                    "operationId": "getConnectedPlatforms",
                    "responses": {
                        "200": {
                            "description": "List of connected platforms",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "type": "array",
                                                "items": {
                                                    "$ref": "#/components/schemas/ConnectedPlatform"
                                                },
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/reports/history": {
                "get": {
                    "summary": "Get generated report image history",
                    "operationId": "getReportHistory",
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "default": 20},
                        },
                        {
                            "name": "offset",
                            "in": "query",
                            "schema": {"type": "integer", "default": 0},
                        },
                        {
                            "name": "group_id",
                            "in": "query",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "search",
                            "in": "query",
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "List of reports",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "items": {
                                                        "type": "array",
                                                        "items": {
                                                            "$ref": "#/components/schemas/ReportItem"
                                                        },
                                                    },
                                                    "total": {"type": "integer"},
                                                    "limit": {"type": "integer"},
                                                    "offset": {"type": "integer"},
                                                },
                                                "required": ["items", "total"],
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/reports/templates": {
                "get": {
                    "summary": "Get available report visual templates",
                    "operationId": "getReportTemplates",
                    "responses": {
                        "200": {
                            "description": "List of templates",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "type": "array",
                                                "items": {
                                                    "$ref": "#/components/schemas/ReportTemplateItem"
                                                },
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/logs": {
                "get": {
                    "summary": "Get live plugin logs with filters",
                    "operationId": "getPluginLogs",
                    "parameters": [
                        {"name": "level", "in": "query", "schema": {"type": "string"}},
                        {"name": "tag", "in": "query", "schema": {"type": "string"}},
                        {
                            "name": "search",
                            "in": "query",
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Logs list and tags",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "$ref": "#/components/schemas/PluginLogResponse"
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/plugin-data/overview": {
                "get": {
                    "summary": "Get size overview for each data partition",
                    "operationId": "getPluginDataOverview",
                    "responses": {
                        "200": {
                            "description": "Storage overview",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "$ref": "#/components/schemas/PluginDataOverview"
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/plugin-data/config-backups": {
                "get": {
                    "summary": "List configuration backups",
                    "operationId": "getConfigBackups",
                    "responses": {
                        "200": {
                            "description": "Backup list",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "items": {
                                                        "type": "array",
                                                        "items": {
                                                            "$ref": "#/components/schemas/ConfigBackupInfo"
                                                        },
                                                    }
                                                },
                                                "required": ["items"],
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/plugin-data/config-backups/detail": {
                "get": {
                    "summary": "Read an original JSON configuration backup",
                    "operationId": "getConfigBackup",
                    "parameters": [
                        {
                            "in": "query",
                            "name": "filename",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Backup JSON",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "$ref": "#/components/schemas/ConfigBackupDetail"
                                            },
                                        },
                                    }
                                }
                            },
                        },
                        "400": {"description": "Invalid backup or filename"},
                        "404": {"description": "Backup no longer exists"},
                    },
                }
            },
            "/openapi.json": {
                "get": {
                    "summary": "Get OpenAPI 3.1 specification for the plugin Web API",
                    "operationId": "getOpenApiSpec",
                    "responses": {
                        "200": {
                            "description": "OpenAPI 3.1 specification JSON",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                }
            },
        },
        "components": {
            "schemas": {
                "GroupItem": {
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string", "minLength": 1},
                        "group_name": {"type": "string"},
                        "platform": {"type": "string"},
                    },
                    "required": ["group_id", "group_name", "platform"],
                },
                "T2iProbeRequest": {
                    "type": "object",
                    "properties": {
                        "render_service": {
                            "type": "string",
                            "enum": ["astrbot", "custom"],
                            "default": "custom",
                        },
                        "group_id": {"type": "string", "maxLength": 256},
                        "platform_id": {"type": "string", "maxLength": 256},
                        "service_endpoint": {
                            "type": "string",
                            "maxLength": 2048,
                            "description": "自定义方案的服务地址，省略时使用 http://127.0.0.1:8999/text2img",
                        },
                        "service_token": {
                            "type": "string",
                            "maxLength": 4096,
                            "writeOnly": True,
                        },
                        "timeout": {
                            "type": "integer",
                            "minimum": 1000,
                            "maximum": 300000,
                            "default": 20000,
                        },
                        "request_timeout": {
                            "type": "integer",
                            "minimum": 1000,
                            "maximum": 300000,
                            "description": "自定义方案的请求等待上限，省略时为 40000 毫秒",
                        },
                    },
                },
                "T2iProbe": {
                    "type": "object",
                    "properties": {
                        "image_data_url": {
                            "type": "string",
                            "pattern": "^data:image/(png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$",
                        },
                        "elapsed_ms": {"type": "number", "minimum": 0},
                    },
                    "required": ["image_data_url", "elapsed_ms"],
                },
                "TemplateCdnProbeRequest": {
                    "type": "object",
                    "properties": {"base_url": {"type": "string", "maxLength": 2048}},
                    "required": ["base_url"],
                },
                "TemplateCdnCheck": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                        "description": {"type": "string"},
                        "kind": {"type": "string", "enum": ["gh", "npm"]},
                        "url": {"type": "string"},
                        "success": {"type": "boolean"},
                        "status_code": {"type": ["integer", "null"]},
                        "elapsed_ms": {"type": "number", "minimum": 0},
                        "error": {"type": ["string", "null"]},
                    },
                    "required": [
                        "id",
                        "label",
                        "description",
                        "kind",
                        "url",
                        "success",
                        "status_code",
                        "elapsed_ms",
                        "error",
                    ],
                },
                "TemplateCdnProbe": {
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string"},
                        "usable": {"type": "boolean"},
                        "checks": {
                            "type": "array",
                            "minItems": 2,
                            "items": {"$ref": "#/components/schemas/TemplateCdnCheck"},
                        },
                    },
                    "required": ["base_url", "usable", "checks"],
                },
                "ActiveTask": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "group_id": {"type": "string"},
                        "group_name": {"type": "string"},
                        "platform": {"type": "string"},
                        "trigger_type": {"type": "string"},
                        "current_stage": {"type": "string"},
                        "started_at": {"type": "number"},
                        "duration_s": {"type": "number"},
                        "last_heartbeat": {"type": "number"},
                    },
                    "required": [
                        "task_id",
                        "group_id",
                        "group_name",
                        "platform",
                        "trigger_type",
                        "current_stage",
                        "started_at",
                        "duration_s",
                        "last_heartbeat",
                    ],
                },
                "ConnectedPlatform": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "label": {"type": "string"},
                    },
                    "required": ["id", "name", "type", "label"],
                },
                "TraceSpan": {
                    "type": "object",
                    "properties": {
                        "span_id": {"type": "string"},
                        "trace_id": {"type": "string"},
                        "stage_name": {"type": "string"},
                        "status": {"type": "string"},
                        "started_at": {"type": "number"},
                        "duration_ms": {"type": "number", "nullable": True},
                        "start_memory_mb": {"type": "number", "nullable": True},
                        "end_memory_mb": {"type": "number", "nullable": True},
                        "delta_memory_mb": {"type": "number", "nullable": True},
                        "payload": {"type": "object", "additionalProperties": True},
                    },
                    "required": [
                        "span_id",
                        "trace_id",
                        "stage_name",
                        "status",
                        "started_at",
                        "payload",
                    ],
                },
                "ContextMetrics": {
                    "type": "object",
                    "properties": {
                        "trace_id": {"type": "string"},
                        "raw_message_count": {"type": "number"},
                        "cleaned_message_count": {"type": "number"},
                        "compression_ratio": {"type": "number"},
                        "incremental_batches": {"type": "number"},
                        "window_size": {"type": "number"},
                    },
                    "required": [
                        "trace_id",
                        "raw_message_count",
                        "cleaned_message_count",
                        "compression_ratio",
                        "incremental_batches",
                        "window_size",
                    ],
                },
                "TokenUsage": {
                    "type": "object",
                    "properties": {
                        "trace_id": {"type": "string"},
                        "prompt_tokens": {"type": "number"},
                        "completion_tokens": {"type": "number"},
                        "total_tokens": {"type": "number"},
                        "estimated_cost": {"type": "number"},
                        "per_analyzer": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "object",
                                "properties": {
                                    "prompt_tokens": {"type": "number"},
                                    "completion_tokens": {"type": "number"},
                                    "total_tokens": {"type": "number"},
                                },
                                "required": [
                                    "prompt_tokens",
                                    "completion_tokens",
                                    "total_tokens",
                                ],
                            },
                        },
                    },
                    "required": [
                        "trace_id",
                        "prompt_tokens",
                        "completion_tokens",
                        "total_tokens",
                        "estimated_cost",
                        "per_analyzer",
                    ],
                },
                "PerformanceMetrics": {
                    "type": "object",
                    "properties": {
                        "trace_id": {"type": "string", "nullable": True},
                        "init_memory_mb": {"type": "number"},
                        "peak_memory_mb": {"type": "number"},
                        "final_memory_mb": {"type": "number"},
                        "delta_memory_mb": {"type": "number"},
                        "metrics_extra": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                    },
                    "required": [
                        "init_memory_mb",
                        "peak_memory_mb",
                        "final_memory_mb",
                        "delta_memory_mb",
                    ],
                },
                "TraceRecord": {
                    "type": "object",
                    "properties": {
                        "trace_id": {"type": "string"},
                        "group_id": {"type": "string"},
                        "group_name": {"type": "string"},
                        "platform": {"type": "string"},
                        "trigger_type": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": [
                                "pending",
                                "running",
                                "succeeded",
                                "completed",
                                "warning",
                                "failed",
                                "aborted",
                                "cancelled",
                                "skipped",
                            ],
                        },
                        "started_at": {"type": "number"},
                        "completed_at": {"type": "number", "nullable": True},
                        "duration_ms": {"type": "number", "nullable": True},
                        "error_stage": {"type": "string", "nullable": True},
                        "error_message": {"type": "string", "nullable": True},
                        "stack_trace": {"type": "string", "nullable": True},
                        "extra": {"type": "object", "additionalProperties": True},
                        "total_tokens": {"type": "number", "nullable": True},
                        "estimated_cost": {"type": "number", "nullable": True},
                        "raw_message_count": {"type": "number", "nullable": True},
                        "cleaned_message_count": {"type": "number", "nullable": True},
                        "compression_ratio": {"type": "number", "nullable": True},
                        "current_stage": {"type": "string", "nullable": True},
                        "spans": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/TraceSpan"},
                        },
                        "context_metrics": {
                            "$ref": "#/components/schemas/ContextMetrics",
                            "nullable": True,
                        },
                        "token_usage": {
                            "$ref": "#/components/schemas/TokenUsage",
                            "nullable": True,
                        },
                        "performance_metrics": {
                            "$ref": "#/components/schemas/PerformanceMetrics",
                            "nullable": True,
                        },
                        "report_files": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "filename": {"type": "string"},
                                    "path": {"type": "string"},
                                    "format": {"type": "string"},
                                    "report_type": {"type": "string"},
                                    "size_bytes": {"type": "number"},
                                    "created_at": {"type": "number"},
                                },
                            },
                        },
                    },
                    "required": [
                        "trace_id",
                        "group_id",
                        "group_name",
                        "platform",
                        "trigger_type",
                        "status",
                        "started_at",
                    ],
                },
                "AnalyticsTrendPoint": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string"},
                        "date_full": {"type": "string"},
                        "timestamp": {"type": "number"},
                        "request_count": {"type": "number"},
                        "succeeded_count": {"type": "number"},
                        "failed_count": {"type": "number"},
                        "prompt_tokens": {"type": "number"},
                        "completion_tokens": {"type": "number"},
                        "total_tokens": {"type": "number"},
                        "estimated_cost": {"type": "number"},
                    },
                    "required": [
                        "date",
                        "date_full",
                        "timestamp",
                        "request_count",
                        "succeeded_count",
                        "failed_count",
                        "prompt_tokens",
                        "completion_tokens",
                        "total_tokens",
                        "estimated_cost",
                    ],
                },
                "ProviderBreakdownItem": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "total_tokens": {"type": "number"},
                        "request_count": {"type": "number"},
                    },
                    "required": ["name", "total_tokens", "request_count"],
                },
                "ModelBreakdownItem": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "total_tokens": {"type": "number"},
                        "request_count": {"type": "number"},
                    },
                    "required": ["name", "total_tokens", "request_count"],
                },
                "AnalyticsTrendsResponse": {
                    "type": "object",
                    "properties": {
                        "granularity": {"type": "string", "enum": ["day", "hour"]},
                        "range_count": {"type": "number"},
                        "points": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/AnalyticsTrendPoint"
                            },
                        },
                        "provider_breakdown": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/ProviderBreakdownItem"
                            },
                        },
                        "model_breakdown": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/ModelBreakdownItem"
                            },
                        },
                    },
                    "required": [
                        "granularity",
                        "range_count",
                        "points",
                        "provider_breakdown",
                        "model_breakdown",
                    ],
                },
                "MetricsSummary": {
                    "type": "object",
                    "properties": {
                        "total_traces": {"type": "number"},
                        "succeeded_count": {"type": "number"},
                        "failed_count": {"type": "number"},
                        "success_rate": {"type": "number"},
                        "avg_duration_ms": {"type": "number"},
                        "today_traces": {"type": "number"},
                        "today_active_groups": {"type": "number"},
                        "total_tokens_spent": {"type": "number"},
                        "total_cost_spent": {"type": "number"},
                        "today_tokens_spent": {"type": "number"},
                        "today_cost_spent": {"type": "number"},
                        "trends": {
                            "$ref": "#/components/schemas/AnalyticsTrendsResponse"
                        },
                    },
                    "required": [
                        "total_traces",
                        "succeeded_count",
                        "failed_count",
                        "success_rate",
                        "avg_duration_ms",
                        "today_traces",
                        "today_active_groups",
                        "total_tokens_spent",
                        "total_cost_spent",
                        "today_tokens_spent",
                        "today_cost_spent",
                    ],
                },
                "ReportItem": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "size_bytes": {"type": "number"},
                        "modified_at": {"type": "number"},
                        "created_at": {"type": "number", "nullable": True},
                        "absolute_path": {"type": "string", "nullable": True},
                        "data_url": {"type": "string", "nullable": True},
                        "is_html": {"type": "boolean", "nullable": True},
                        "is_comic": {"type": "boolean", "nullable": True},
                        "report_type": {
                            "type": "string",
                            "enum": ["image", "html", "comic"],
                            "nullable": True,
                        },
                        "html_content": {"type": "string", "nullable": True},
                        "group_id": {"type": "string", "nullable": True},
                        "group_name": {"type": "string", "nullable": True},
                        "platform": {"type": "string", "nullable": True},
                        "trace_id": {"type": "string", "nullable": True},
                    },
                    "required": ["filename", "size_bytes", "modified_at"],
                },
                "ReportTemplateItem": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                        "display_name": {"type": "string", "nullable": True},
                        "desc": {"type": "string", "nullable": True},
                        "tag": {"type": "string", "nullable": True},
                        "tag_color": {"type": "string", "nullable": True},
                        "is_custom": {"type": "boolean", "nullable": True},
                        "can_uninstall": {"type": "boolean", "nullable": True},
                        "has_image": {"type": "boolean", "nullable": True},
                        "has_html": {"type": "boolean", "nullable": True},
                    },
                    "required": ["id", "label"],
                },
                "PluginLogItem": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "timestamp": {"type": "number"},
                        "time_str": {"type": "string"},
                        "level": {
                            "type": "string",
                            "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        },
                        "logger_name": {"type": "string"},
                        "tag": {"type": "string"},
                        "message": {"type": "string"},
                        "raw": {"type": "string"},
                        "trace_id": {"type": "string", "nullable": True},
                        "stage": {"type": "string", "nullable": True},
                        "location": {"type": "string", "nullable": True},
                    },
                    "required": [
                        "id",
                        "timestamp",
                        "time_str",
                        "level",
                        "logger_name",
                        "tag",
                        "message",
                        "raw",
                    ],
                },
                "AvailableTag": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "label": {"type": "string"},
                    },
                    "required": ["key", "label"],
                },
                "PluginLogResponse": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/PluginLogItem"},
                        },
                        "total": {"type": "integer"},
                        "available_tags": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/AvailableTag"},
                        },
                    },
                    "required": ["items", "total", "available_tags"],
                },
                "ConfigBackupInfo": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "size_bytes": {"type": "integer"},
                        "kind": {
                            "type": "string",
                            "enum": ["upgrade", "comic_migration", "other"],
                        },
                        "plugin_version": {"type": "string", "nullable": True},
                        "saved_at": {"type": "string", "nullable": True},
                        "error": {"type": "string", "nullable": True},
                    },
                    "required": [
                        "filename",
                        "size_bytes",
                        "kind",
                        "plugin_version",
                        "saved_at",
                        "error",
                    ],
                },
                "ConfigBackupDetail": {
                    "type": "object",
                    "properties": {
                        "backup": {"$ref": "#/components/schemas/ConfigBackupInfo"},
                        "content": {"$ref": "#/components/schemas/BackupJsonValue"},
                    },
                    "required": ["backup", "content"],
                },
                "BackupJsonValue": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "number"},
                        {"type": "boolean"},
                        {"type": "null"},
                        {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/BackupJsonValue"},
                        },
                        {
                            "type": "object",
                            "additionalProperties": {
                                "$ref": "#/components/schemas/BackupJsonValue"
                            },
                        },
                    ],
                },
                "SectionStats": {
                    "type": "object",
                    "properties": {
                        "count": {"type": "number"},
                        "size_bytes": {"type": "number"},
                    },
                    "required": ["count", "size_bytes"],
                },
                "PluginDataOverview": {
                    "type": "object",
                    "properties": {
                        "avatars": {"$ref": "#/components/schemas/SectionStats"},
                        "custom_templates": {
                            "$ref": "#/components/schemas/SectionStats"
                        },
                        "config_files": {"$ref": "#/components/schemas/SectionStats"},
                        "config_backups": {"$ref": "#/components/schemas/SectionStats"},
                        "reports": {"$ref": "#/components/schemas/SectionStats"},
                        "temp_files": {"$ref": "#/components/schemas/SectionStats"},
                    },
                    "required": [
                        "avatars",
                        "custom_templates",
                        "config_files",
                        "config_backups",
                        "reports",
                        "temp_files",
                    ],
                },
                "IncrementalBatchTopic": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "description": {"type": "string"},
                        "heat_score": {"type": "number"},
                        "category": {"type": "string"},
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "additionalProperties": True,
                },
                "ChatQualityDimension": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "percentage": {"type": "number"},
                        "comment": {"type": "string"},
                        "color": {"type": "string"},
                    },
                },
                "ChatQualityReviewObject": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "subtitle": {"type": "string"},
                        "dimensions": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/ChatQualityDimension"
                            },
                        },
                        "summary": {"type": "string"},
                    },
                },
                "IncrementalBatchGoldenQuote": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "text": {"type": "string"},
                        "sender_nickname": {"type": "string"},
                        "sender_name": {"type": "string"},
                        "author": {"type": "string"},
                    },
                    "additionalProperties": True,
                },
                "IncrementalBatchItem": {
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string"},
                        "batch_id": {"type": "string"},
                        "timestamp": {"type": "number"},
                        "created_at_iso": {"type": "string"},
                        "messages_count": {"type": "number"},
                        "characters_count": {"type": "number"},
                        "topics_count": {"type": "number"},
                        "topics": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/IncrementalBatchTopic"
                            },
                        },
                        "golden_quotes_count": {"type": "number"},
                        "golden_quotes": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/IncrementalBatchGoldenQuote"
                            },
                        },
                        "hourly_msg_counts": {
                            "type": "object",
                            "additionalProperties": {"type": "number"},
                        },
                        "hourly_char_counts": {
                            "type": "object",
                            "additionalProperties": {"type": "number"},
                        },
                        "token_usage": {
                            "type": "object",
                            "properties": {
                                "prompt_tokens": {"type": "number"},
                                "completion_tokens": {"type": "number"},
                                "total_tokens": {"type": "number"},
                            },
                            "additionalProperties": True,
                        },
                        "last_message_timestamp": {"type": "number"},
                        "participant_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "group_id",
                        "batch_id",
                        "timestamp",
                        "messages_count",
                        "characters_count",
                        "topics_count",
                    ],
                    "additionalProperties": True,
                },
                "IncrementalCursorInfo": {
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string"},
                        "last_analyzed_timestamp": {"type": "number"},
                        "last_message_timestamp": {"type": "number"},
                        "tracked_message_ids_count": {"type": "number"},
                    },
                    "required": [
                        "group_id",
                        "last_analyzed_timestamp",
                        "last_message_timestamp",
                        "tracked_message_ids_count",
                    ],
                },
                "IncrementalBatchesResponse": {
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string"},
                        "cursor": {
                            "$ref": "#/components/schemas/IncrementalCursorInfo"
                        },
                        "batches": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/IncrementalBatchItem"
                            },
                        },
                    },
                    "required": ["group_id", "cursor", "batches"],
                },
                "CheckpointItem": {
                    "type": "object",
                    "properties": {
                        "checkpoint_id": {"type": "string"},
                        "group_id": {"type": "string"},
                        "date_str": {"type": "string"},
                        "stage_name": {"type": "string"},
                        "trace_id": {"type": "string"},
                        "data_size_bytes": {"type": "number"},
                        "data_size": {"type": "number"},
                        "created_at": {"type": "number"},
                        "created_at_formatted": {"type": "string"},
                        "updated_at": {"type": "string"},
                        "expire_at": {"type": "number"},
                        "has_data": {"type": "boolean"},
                    },
                    "required": ["group_id", "date_str", "stage_name"],
                },
                "CheckpointsListResponse": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/CheckpointItem"},
                        },
                        "total": {"type": "number"},
                    },
                    "required": ["items", "total"],
                },
                "CheckpointDetail": {
                    "type": "object",
                    "properties": {
                        "checkpoint_id": {"type": "string"},
                        "group_id": {"type": "string"},
                        "date_str": {"type": "string"},
                        "stage_name": {"type": "string"},
                        "trace_id": {"type": "string"},
                        "data": {"type": "object", "additionalProperties": True},
                        "checkpoint_data": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                        "data_size_bytes": {"type": "number"},
                        "data_size": {"type": "number"},
                        "created_at": {"type": "number"},
                        "created_at_formatted": {"type": "string"},
                        "expire_at": {"type": "number"},
                    },
                    "required": ["group_id", "date_str", "stage_name"],
                },
            }
        },
    }
