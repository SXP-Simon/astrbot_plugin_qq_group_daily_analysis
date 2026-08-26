import React, { useState } from "react";
import {
  Form,
  Switch,
  InputNumber,
  Select,
  Input,
  AutoComplete,
  Tag,
  Space,
  Typography,
  Tooltip,
  Button,
  theme,
} from "antd";
import {
  PlusOutlined,
  UndoOutlined,
  ApartmentOutlined,
} from "@ant-design/icons";
import { SchemaFieldItem } from "../../../entities/config/model/types";
import { AvailableProvider } from "../../../entities/config/api/configApi";
import { TemplateListRenderer } from "./TemplateListRenderer";

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

interface FieldRendererProps {
  fieldKey: string;
  fieldSchema: SchemaFieldItem;
  value: unknown;
  providers?: AvailableProvider[];
  isSubField?: boolean;
  onChange: (val: unknown) => void;
}

export const FieldRenderer: React.FC<FieldRendererProps> = ({
  fieldKey,
  fieldSchema,
  value,
  providers = [],
  isSubField = false,
  onChange,
}) => {
  const { token } = theme.useToken();
  const [newTagInput, setNewTagInput] = useState("");
  const [isAddingTag, setIsAddingTag] = useState(false);

  const title = fieldSchema.description || fieldKey;
  const hint = fieldSchema.hint || "";
  const type = fieldSchema.type;
  const options = fieldSchema.options;
  const defaultValue = fieldSchema.default;

  // 1. 判断是否为 Provider 选择字段
  const isProviderField =
    type === "string" &&
    (fieldKey.toLowerCase().includes("provider") ||
      fieldKey.toLowerCase().includes("provider_id") ||
      fieldSchema._special === "select_provider");

  // 渲染不同的表单控件
  const renderControl = () => {
    // 0. 特殊结构：template_list (如 drawing_provider_overrides / comic_characters)
    if (type === "template_list") {
      return (
        <TemplateListRenderer
          fieldKey={fieldKey}
          fieldSchema={fieldSchema}
          value={value}
          providers={providers}
          onChange={onChange}
        />
      );
    }

    // 1. Provider 智能选择输入框 (支持选择已装配的 AstrBot Provider 或自由手输)
    if (isProviderField) {
      const currentVal = value !== undefined ? String(value) : String(defaultValue ?? "");
      const providerOptions = [
        {
          value: "",
          label: "（留空使用当前会话默认 Provider）",
        },
        ...providers.map((p) => ({
          value: p.id,
          label: `${p.name || p.id} [${p.id}]${p.type ? ` (${p.type})` : ""}`,
        })),
      ];

      return (
        <AutoComplete
          value={currentVal}
          options={providerOptions}
          onChange={(v) => onChange(v)}
          style={{ width: "100%" }}
          placeholder="可从下拉列表选择已有 Provider，或直接输入 ID"
          filterOption={(inputValue, option) =>
            String(option?.label || "")
              .toLowerCase()
              .includes(inputValue.toLowerCase()) ||
            String(option?.value || "")
              .toLowerCase()
              .includes(inputValue.toLowerCase())
          }
        >
          <Input
            prefix={<ApartmentOutlined style={{ color: "#2563eb", marginRight: 4 }} />}
            allowClear
          />
        </AutoComplete>
      );
    }

    // 2. 布尔类型开关 Switch
    if (type === "bool") {
      const boolVal = typeof value === "boolean" ? value : Boolean(defaultValue);
      return (
        <div style={{ display: "flex", alignItems: "center", gap: 10, minHeight: 32 }}>
          <Switch
            checked={boolVal}
            onChange={(checked) => onChange(checked)}
          />
          <Text style={{ fontSize: 12, color: boolVal ? "#16a34a" : "#8c8c8c" }}>
            {boolVal ? "已启用" : "已关闭"}
          </Text>
        </div>
      );
    }

    // 3. 单选下拉框 (带有 options 的 string)
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

    // 4. 数字类型输入框 (int / float)
    if (type === "int" || type === "float") {
      const numVal =
        typeof value === "number"
          ? value
          : typeof defaultValue === "number"
            ? defaultValue
            : 0;
      return (
        <InputNumber
          value={numVal}
          onChange={(v) => onChange(v ?? 0)}
          step={type === "float" ? 0.1 : 1}
          style={{ width: "100%" }}
        />
      );
    }

    // 5. 多选下拉框 (带有 options 的 list)
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

    // 6. 字符串列表标签编辑器 (无 options 的 list，如 白名单列表、bot_self_ids)
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
            background: token.colorFillAlter,
            border: `1px solid ${token.colorBorderSecondary}`,
            borderRadius: 4,
            minHeight: 36,
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
                  background: token.colorBgContainer,
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

    // 7. 长文本 / 提示词 (Prompt / Multiline String / text)
    const isMultiline =
      type === "text" ||
      fieldKey.includes("prompt") ||
      fieldKey.includes("template") ||
      (typeof value === "string" && (value.includes("\n") || value.length > 60));

    if ((type === "string" || type === "text") && isMultiline) {
      const strVal = typeof value === "string" ? value : String(defaultValue ?? "");
      return (
        <TextArea
          value={strVal}
          onChange={(e) => onChange(e.target.value)}
          autoSize={{ minRows: 2, maxRows: 8 }}
          style={{
            fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
            fontSize: 12,
          }}
        />
      );
    }

    // 8. 普通短文本输入框
    if (type === "string" || type === "text" || type === "file") {
      const strVal = typeof value === "string" ? value : String(defaultValue ?? "");
      return (
        <Input
          value={strVal}
          onChange={(e) => onChange(e.target.value)}
          allowClear
        />
      );
    }

    // 9. 复杂对象 / 数组 (Fallback JSON Editor)
    const jsonStr =
      typeof value === "object"
        ? JSON.stringify(value, null, 2)
        : String(value ?? "");
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
    defaultValue !== undefined &&
    JSON.stringify(value) !== JSON.stringify(defaultValue);

  return (
    <Form.Item
      label={
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            width: "100%",
          }}
        >
          <Space size={6}>
            <Text strong style={{ fontSize: isSubField ? 12 : 13, color: token.colorText }}>
              {title}
            </Text>
            {!isSubField && (
              <span
                style={{
                  fontSize: 11,
                  fontFamily: "monospace",
                  color: token.colorTextTertiary,
                }}
              >
                ({fieldKey})
              </span>
            )}
          </Space>

          {isDifferentFromDefault && (
            <Tooltip title="重置为此项默认值">
              <Button
                type="link"
                size="small"
                icon={<UndoOutlined style={{ fontSize: 10 }} />}
                style={{
                  padding: "0 4px",
                  height: "auto",
                  fontSize: 11,
                  color: token.colorTextTertiary,
                }}
                onClick={() => onChange(defaultValue)}
              >
                恢复默认
              </Button>
            </Tooltip>
          )}
        </div>
      }
      style={{
        marginBottom: isSubField ? 10 : 16,
        padding: isSubField
          ? 0
          : "10px 12px",
        background: isSubField ? "transparent" : token.colorBgContainer,
        border: isSubField ? "none" : `1px solid ${token.colorBorderSecondary}`,
        borderRadius: 6,
      }}
    >
      {renderControl()}
      {hint && (
        <Paragraph
          type="secondary"
          style={{
            fontSize: 11,
            lineHeight: "1.4",
            marginTop: 5,
            marginBottom: 0,
            color: token.colorTextSecondary,
          }}
        >
          {hint}
        </Paragraph>
      )}
    </Form.Item>
  );
};
