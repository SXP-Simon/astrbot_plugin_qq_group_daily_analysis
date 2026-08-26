import React, { useState } from "react";
import {
  Form,
  Switch,
  InputNumber,
  Select,
  Input,
  Tag,
  Typography,
  Tooltip,
  Button,
} from "antd";
import { PlusOutlined, UndoOutlined } from "@ant-design/icons";
import { SchemaFieldItem } from "../../../entities/config/model/types";
import { useTheme } from "../../../shared/lib/useTheme";

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

interface FieldRendererProps {
  fieldKey: string;
  fieldSchema: SchemaFieldItem;
  value: unknown;
  onChange: (val: unknown) => void;
}

export const FieldRenderer: React.FC<FieldRendererProps> = ({
  fieldKey,
  fieldSchema,
  value,
  onChange,
}) => {
  const { isDark } = useTheme();
  const [newTagInput, setNewTagInput] = useState("");
  const [isAddingTag, setIsAddingTag] = useState(false);

  const title = fieldSchema.description || fieldKey;
  const hint = fieldSchema.hint || "";
  const type = fieldSchema.type;
  const options = fieldSchema.options;
  const defaultValue = fieldSchema.default;

  // 渲染不同的表单控件
  const renderControl = () => {
    // 1. 布尔类型开关 Switch
    if (type === "bool") {
      const boolVal = typeof value === "boolean" ? value : Boolean(defaultValue);
      return (
        <div style={{ display: "flex", alignItems: "center", gap: 10, minHeight: 32 }}>
          <Switch
            checked={boolVal}
            onChange={(checked) => onChange(checked)}
          />
          <Text style={{ fontSize: 12, color: boolVal ? "#52c41a" : "#8c8c8c" }}>
            {boolVal ? "已启用" : "已关闭"}
          </Text>
        </div>
      );
    }

    // 2. 单选下拉框 (带有 options 的 string)
    if (type === "string" && Array.isArray(options) && options.length > 0) {
      const currentVal = value !== undefined ? String(value) : String(defaultValue ?? "");
      return (
        <Select
          value={currentVal}
          onChange={(v) => onChange(v)}
          style={{ width: "100%" }}
          options={options.map((opt) => ({
            label: String(opt),
            value: String(opt),
          }))}
        />
      );
    }

    // 3. 数字类型输入框 (int / float)
    if (type === "int" || type === "float") {
      const numVal = typeof value === "number" ? value : typeof defaultValue === "number" ? defaultValue : 0;
      return (
        <InputNumber
          value={numVal}
          onChange={(v) => onChange(v ?? 0)}
          step={type === "float" ? 0.1 : 1}
          style={{ width: "100%" }}
        />
      );
    }

    // 4. 多选下拉框 (带有 options 的 list)
    if (type === "list" && Array.isArray(options) && options.length > 0) {
      const currentList: string[] = Array.isArray(value)
        ? (value as string[])
        : Array.isArray(defaultValue)
          ? (defaultValue as string[])
          : [];
      return (
        <Select
          mode="multiple"
          value={currentList}
          onChange={(v) => onChange(v)}
          style={{ width: "100%" }}
          options={options.map((opt) => ({
            label: String(opt),
            value: String(opt),
          }))}
        />
      );
    }

    // 5. 字符串列表标签编辑器 (无 options 的 list，如 白名单列表、bot_self_ids)
    if (type === "list" && (!options || options.length === 0)) {
      const currentList: string[] = Array.isArray(value)
        ? (value as string[]).map(String)
        : Array.isArray(defaultValue)
          ? (defaultValue as string[]).map(String)
          : [];

      const handleRemoveTag = (removedIndex: number) => {
        const next = currentList.filter((_, idx) => idx !== removedIndex);
        onChange(next);
      };

      const handleAddTag = () => {
        if (newTagInput.trim()) {
          const next = [...currentList, newTagInput.trim()];
          onChange(next);
          setNewTagInput("");
          setIsAddingTag(false);
        }
      };

      return (
        <div
          style={{
            padding: "6px 8px",
            background: isDark ? "#141414" : "#f9f9f9",
            border: `1px solid ${isDark ? "#303030" : "#d9d9d9"}`,
            borderRadius: 4,
            minHeight: 40,
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
            {currentList.map((tagStr, idx) => (
              <Tag
                key={`${tagStr}-${idx}`}
                closable
                onClose={(e) => {
                  e.preventDefault();
                  handleRemoveTag(idx);
                }}
                style={{ margin: 0 }}
              >
                {tagStr}
              </Tag>
            ))}

            {isAddingTag ? (
              <Input
                size="small"
                style={{ width: 140 }}
                value={newTagInput}
                onChange={(e) => setNewTagInput(e.target.value)}
                onBlur={handleAddTag}
                onPressEnter={handleAddTag}
                placeholder="输入后回车"
                autoFocus
              />
            ) : (
              <Tag
                onClick={() => setIsAddingTag(true)}
                style={{
                  background: isDark ? "#262626" : "#fff",
                  borderStyle: "dashed",
                  cursor: "pointer",
                  margin: 0,
                }}
              >
                <PlusOutlined /> 添加条目
              </Tag>
            )}
          </div>
        </div>
      );
    }

    // 6. 长文本 / 提示词 (Prompt / Multiline String)
    const isMultiline =
      fieldKey.includes("prompt") ||
      fieldKey.includes("template") ||
      (typeof value === "string" && (value.includes("\n") || value.length > 60));

    if (type === "string" && isMultiline) {
      const strVal = typeof value === "string" ? value : String(defaultValue ?? "");
      return (
        <TextArea
          value={strVal}
          onChange={(e) => onChange(e.target.value)}
          autoSize={{ minRows: 2, maxRows: 8 }}
          style={{
            fontFamily: "monospace",
            fontSize: 12,
          }}
        />
      );
    }

    // 7. 普通短文本输入框
    if (type === "string") {
      const strVal = typeof value === "string" ? value : String(defaultValue ?? "");
      return (
        <Input
          value={strVal}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    }

    // 8. 复杂对象 / 数组 (Fallback JSON Editor)
    const jsonStr = typeof value === "object" ? JSON.stringify(value, null, 2) : String(value ?? "");
    return (
      <TextArea
        value={jsonStr}
        onChange={(e) => {
          try {
            const parsed = JSON.parse(e.target.value);
            onChange(parsed);
          } catch {
            // 保持临时输入
          }
        }}
        autoSize={{ minRows: 2, maxRows: 6 }}
        style={{ fontFamily: "monospace", fontSize: 11 }}
      />
    );
  };

  const isDifferentFromDefault =
    defaultValue !== undefined && JSON.stringify(value) !== JSON.stringify(defaultValue);

  return (
    <Form.Item
      label={
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
          <Text strong style={{ fontSize: 13 }}>
            {title}
          </Text>
          {isDifferentFromDefault && (
            <Tooltip title="重置为此项默认值">
              <Button
                type="link"
                size="small"
                icon={<UndoOutlined style={{ fontSize: 11 }} />}
                style={{ padding: "0 4px", height: "auto", fontSize: 11, color: "#8c8c8c" }}
                onClick={() => onChange(defaultValue)}
              >
                恢复默认
              </Button>
            </Tooltip>
          )}
        </div>
      }
      style={{ marginBottom: 16 }}
    >
      {renderControl()}
      {hint && (
        <Paragraph
          type="secondary"
          style={{
            fontSize: 11,
            lineHeight: "1.4",
            marginTop: 4,
            marginBottom: 0,
            color: isDark ? "#8c8c8c" : "#8c8c8c",
          }}
        >
          {hint}
        </Paragraph>
      )}
    </Form.Item>
  );
};
