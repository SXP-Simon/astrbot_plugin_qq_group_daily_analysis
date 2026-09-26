"""OpenAPI 3.1 specification provider for AstrBot QQ Group Daily Analysis Web API.

This module builds and provides the complete OpenAPI 3.1 schema definition
for all REST and SSE endpoints served by the plugin dashboard.
"""

from __future__ import annotations

from typing import Any


def generate_openapi_spec() -> dict[str, Any]:
    """Generate OpenAPI 3.1 specification for the plugin web API.

    Returns:
        dict[str, Any]: Complete OpenAPI 3.1 specification dictionary.
    """
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "AstrBot QQ Group Daily Analysis Web API",
            "version": "5.6.4",
            "description": "REST API and data contract specification for AstrBot QQ Group Daily Analysis Dashboard",
        },
        "paths": {
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
                            "description": "List of group IDs",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "data": {
                                                "type": "array",
                                                "items": {"type": "string"},
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
                                                "type": "array",
                                                "items": {
                                                    "$ref": "#/components/schemas/ReportItem"
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
                                "running",
                                "succeeded",
                                "warning",
                                "failed",
                                "aborted",
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
