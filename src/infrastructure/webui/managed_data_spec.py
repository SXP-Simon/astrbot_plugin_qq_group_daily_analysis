"""文件分区管理的 OpenAPI 契约。"""

FILE_SCHEMAS = {
    "ManagedPartition": {
        "type": "object",
        "properties": {
            **{
                key: {"type": "string"}
                for key in ("key", "name", "directory", "description", "impact")
            },
            **{key: {"type": "boolean"} for key in ("writable", "deletable")},
            **{key: {"type": "integer"} for key in ("count", "size_bytes")},
        },
        "required": [
            "key",
            "name",
            "directory",
            "description",
            "impact",
            "writable",
            "deletable",
            "count",
            "size_bytes",
        ],
    },
    "ManagedFile": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "revision": {"type": "string"},
            "size_bytes": {"type": "integer"},
            "modified_at": {"type": "number"},
            "media_type": {"type": "string"},
            "editable": {"type": "boolean"},
            "downloadable": {"type": "boolean"},
        },
        "required": [
            "revision",
            "name",
            "size_bytes",
            "modified_at",
            "media_type",
            "editable",
            "downloadable",
        ],
    },
    "ManagedFileContent": {
        "type": "object",
        "properties": {
            **{
                key: {"type": "string"}
                for key in ("name", "content_base64", "revision", "media_type")
            },
            "text": {"type": ["string", "null"]},
        },
        "required": ["name", "content_base64", "text", "revision", "media_type"],
    },
    "ManagedFileMutation": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            **{
                key: {"type": "string"}
                for key in (
                    "partition",
                    "name",
                    "revision",
                    "content_base64",
                    "new_name",
                )
            },
            "operation": {
                "type": "string",
                "enum": ["create", "replace", "rename", "delete"],
            },
        },
        "required": ["partition", "name", "operation"],
    },
}

FILE_PATHS: dict[str, object] = {}
for path, operation, data, parameters in (
    (
        "partitions",
        "getManagedPartitions",
        {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/ManagedPartition"},
                }
            },
            "required": ["items"],
        },
        [],
    ),
    (
        "files",
        "getManagedFiles",
        {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/ManagedFile"},
                },
                "total": {"type": "integer"},
            },
            "required": ["items", "total"],
        },
        ["partition", "search", "page", "page_size", "extensions"],
    ),
    (
        "files/content",
        "getManagedFileContent",
        {"$ref": "#/components/schemas/ManagedFileContent"},
        ["partition", "name"],
    ),
    (
        "files/mutate",
        "mutateManagedFile",
        {
            "type": "object",
            "properties": {"success": {"type": "boolean"}},
            "required": ["success"],
        },
        [],
    ),
):
    method = "post" if path == "files/mutate" else "get"
    endpoint: dict[str, object] = {
        "operationId": operation,
        "summary": operation,
        "responses": {
            "200": {
                "description": "操作成功",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {"status": {"type": "string"}, "data": data},
                            "required": ["status", "data"],
                        }
                    }
                },
            },
            "400": {"description": "不支持的操作或非法文件"},
            "404": {"description": "文件不存在"},
            "409": {"description": "文件已变更或目标已存在"},
            "500": {"description": "目录读取或文件操作失败"},
        },
    }
    if parameters:
        endpoint["parameters"] = [
            {
                "in": "query",
                "name": name,
                "required": name in {"partition", "name"},
                "schema": {
                    "type": "integer" if name in {"page", "page_size"} else "string"
                },
            }
            for name in parameters
        ]
    if method == "post":
        endpoint["requestBody"] = {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ManagedFileMutation"}
                }
            },
        }
    FILE_PATHS[f"/plugin-data/{path}"] = {method: endpoint}

RECORD_SCHEMAS = {
    "RecordLocator": {
        "type": "object",
        "properties": {
            key: {"type": "string"}
            for key in (
                "kind",
                "key",
                "group_id",
                "batch_id",
                "date_str",
                "stage_name",
                "trace_id",
            )
        },
        "required": ["kind"],
    },
    "ManagedRecord": {
        "type": "object",
        "properties": {
            "locator": {"$ref": "#/components/schemas/RecordLocator"},
            "data": {"$ref": "#/components/schemas/BackupJsonValue"},
            "revision": {"type": "string"},
        },
        "required": ["locator", "data", "revision"],
    },
    "ManagedRecordEntry": {
        "type": "object",
        "properties": {
            "locator": {"$ref": "#/components/schemas/RecordLocator"},
            "name": {"type": "string"},
            "size_bytes": {"type": "integer"},
        },
        "required": ["locator", "name", "size_bytes"],
    },
    "ManagedRecordMutation": {
        "type": "object",
        "properties": {
            "locator": {"$ref": "#/components/schemas/RecordLocator"},
            "operation": {"type": "string", "enum": ["create", "replace", "delete"]},
            "data": {"$ref": "#/components/schemas/BackupJsonValue"},
            "revision": {"type": "string"},
        },
        "required": ["locator", "operation"],
    },
}
RECORD_PATHS: dict[str, object] = {}
for path, operation, data, parameters in (
    (
        "records",
        "listManagedRecords",
        {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/ManagedRecordEntry"},
                },
                "total": {"type": "integer"},
            },
            "required": ["items", "total"],
        },
        ["kind", "search", "page"],
    ),
    (
        "records/detail",
        "getManagedRecord",
        {"$ref": "#/components/schemas/ManagedRecord"},
        ["kind", "key", "group_id", "batch_id", "date_str", "stage_name", "trace_id"],
    ),
    (
        "records/mutate",
        "mutateManagedRecord",
        {
            "type": "object",
            "properties": {"success": {"type": "boolean"}},
            "required": ["success"],
        },
        [],
    ),
):
    method = "post" if path.endswith("mutate") else "get"
    endpoint = {
        "operationId": operation,
        "summary": operation,
        "responses": {
            "200": {
                "description": "操作成功",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {"status": {"type": "string"}, "data": data},
                            "required": ["status", "data"],
                        }
                    }
                },
            },
            "400": {"description": "非法记录或不支持的操作"},
            "404": {"description": "记录不存在或已过期"},
            "409": {"description": "记录冲突或群任务正在执行"},
            "500": {"description": "存储操作失败"},
            "503": {"description": "存储暂不可用"},
        },
    }
    if parameters:
        endpoint["parameters"] = [
            {
                "in": "query",
                "name": name,
                "required": name == "kind",
                "schema": {"type": "integer" if name == "page" else "string"},
            }
            for name in parameters
        ]
    if method == "post":
        endpoint["requestBody"] = {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ManagedRecordMutation"}
                }
            },
        }
    RECORD_PATHS[f"/plugin-data/{path}"] = {method: endpoint}

FILE_SCHEMAS["ManagedFileDeleteMany"] = {
    "type": "object",
    "properties": {
        "partition": {"type": "string"},
        "files": {
            "type": "array",
            "minItems": 1,
            "maxItems": 200,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "revision": {"type": "string"},
                },
                "required": ["name", "revision"],
            },
        },
    },
    "required": ["partition", "files"],
}
FILE_SCHEMAS["ManagedFileDeleteResult"] = {
    "type": "object",
    "properties": {
        "deleted": {"type": "array", "items": {"type": "string"}},
        "failed": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["name", "message"],
            },
        },
    },
    "required": ["deleted", "failed"],
}
FILE_PATHS["/plugin-data/files/delete-many"] = {
    "post": {
        "operationId": "deleteManagedFiles",
        "summary": "Delete only selected files with revisions",
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ManagedFileDeleteMany"}
                }
            },
        },
        "responses": {
            "200": {
                "description": "逐项操作结果，允许部分成功",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "data": {
                                    "$ref": "#/components/schemas/ManagedFileDeleteResult"
                                },
                            },
                            "required": ["status", "data"],
                        }
                    }
                },
            },
            "400": {"description": "非法分区或选择列表"},
        },
    }
}
