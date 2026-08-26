import React, { useState } from "react";
import {
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
  Image,
  theme,
} from "antd";
import {
  PlusOutlined,
  UndoOutlined,
  ApartmentOutlined,
  UserOutlined,
  FileOutlined,
  UploadOutlined,
  DeleteOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import { SchemaFieldItem } from "../../../entities/config/model/types";
import {
  AvailableProvider,
  AvailablePersona,
} from "../../../entities/config/api/configApi";
import { useTheme } from "../../../shared/lib/useTheme";
import { TemplateListRenderer } from "./TemplateListRenderer";

const { Text } = Typography;
const { TextArea } = Input;

const SANS_MONO_FONT =
  "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace";

interface FieldRendererProps {
  fieldKey: string;
  fieldSchema: SchemaFieldItem;
  value: unknown;
  providers?: AvailableProvider[];
  personas?: AvailablePersona[];
  isSubField?: boolean;
  onChange: (val: unknown) => void;
}

export const FieldRenderer: React.FC<FieldRendererProps> = ({
  fieldKey,
  fieldSchema,
  value,
  providers = [],
  personas = [],
  isSubField = false,
  onChange,
}) => {
  const { token } = theme.useToken();
  const { isDark } = useTheme();
  const [newTagInput, setNewTagInput] = useState("");
  const [isAddingTag, setIsAddingTag] = useState(false);
  const [newFileInput, setNewFileInput] = useState("");
  const [isAddingFile, setIsAddingFile] = useState(false);

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

  // 2. 判断是否为 Persona 人设选择字段
  const isPersonaField =
    type === "string" &&
    (fieldKey.toLowerCase().includes("persona") ||
      fieldKey.toLowerCase().includes("persona_id") ||
      fieldSchema._special === "select_persona");

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
          personas={personas}
          onChange={onChange}
        />
      );
    }

    // 0.1 特殊结构：嵌套 object 对象（如 topic_analysis_prompts / user_title_analysis_prompts / golden_quote_analysis_prompts）
    if (
      type === "object" &&
      fieldSchema.items &&
      typeof fieldSchema.items === "object" &&
      !Array.isArray(fieldSchema.items)
    ) {
      const subItems = fieldSchema.items as Record<string, SchemaFieldItem>;
      const objVal =
        typeof value === "object" && value !== null
          ? (value as Record<string, unknown>)
          : {};

      return (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 10,
            width: "100%",
          }}
        >
          {Object.entries(subItems).map(([subKey, subField]) => {
            if (subField.invisible || subField.hidden) return null;
            const subValue =
              objVal[subKey] !== undefined ? objVal[subKey] : subField.default;

            return (
              <FieldRenderer
                key={subKey}
                fieldKey={subKey}
                fieldSchema={subField}
                value={subValue}
                providers={providers}
                personas={personas}
                isSubField={true}
                onChange={(newSubVal) => {
                  const nextObj = { ...objVal, [subKey]: newSubVal };
                  onChange(nextObj);
                }}
              />
            );
          })}
        </div>
      );
    }

    // 1. Provider 智能选择输入框 (支持选择已装配的 AstrBot Provider 或自由手输)
    if (isProviderField) {
      const currentVal =
        typeof value === "string"
          ? value
          : typeof defaultValue === "string"
          ? defaultValue
          : "";
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
            prefix={
              <ApartmentOutlined style={{ color: "#2563eb", marginRight: 4 }} />
            }
            allowClear
            style={{ fontFamily: SANS_MONO_FONT }}
          />
        </AutoComplete>
      );
    }

    // 2. Persona 人设智能选择输入框 (支持选择 AstrBot 内部已定义人设或手输)
    if (isPersonaField) {
      const currentVal =
        typeof value === "string"
          ? value
          : typeof defaultValue === "string"
          ? defaultValue
          : "";
      const personaOptions = [
        {
          value: "",
          label: "（留空使用当前群聊会话/全局默认人设）",
        },
        ...personas.map((p) => ({
          value: p.id,
          label: `${p.name || p.id} [${p.id}]`,
        })),
      ];

      return (
        <AutoComplete
          value={currentVal}
          options={personaOptions}
          onChange={(v) => onChange(v)}
          style={{ width: "100%" }}
          placeholder="可从下拉列表选择已有 Persona 人设，或直接输入人设 ID"
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
            prefix={
              <UserOutlined style={{ color: "#7c3aed", marginRight: 4 }} />
            }
            allowClear
            style={{ fontFamily: SANS_MONO_FONT }}
          />
        </AutoComplete>
      );
    }

    // 3. 布尔类型开关 Switch
    if (type === "bool") {
      const boolVal =
        typeof value === "boolean" ? value : Boolean(defaultValue);
      return (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            minHeight: 32,
          }}
        >
          <Switch
            checked={boolVal}
            onChange={(checked) => onChange(checked)}
          />
          <Text
            style={{
              fontSize: 12,
              fontWeight: 500,
              color: boolVal ? "#16a34a" : token.colorTextTertiary,
            }}
          >
            {boolVal ? "已启用" : "已关闭"}
          </Text>
        </div>
      );
    }

    // 4. 单选下拉框 (带有 options 的 string)
    if (type === "string" && Array.isArray(options) && options.length > 0) {
      const currentVal =
        typeof value === "string"
          ? value
          : typeof defaultValue === "string"
          ? defaultValue
          : "";
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

    // 5. 纯文本 / 提示词模板 (text 或 multiline)
    if (type === "text" || (type === "string" && (fieldKey.includes("template") || fieldKey.includes("prompt")))) {
      const currentVal =
        typeof value === "string"
          ? value
          : typeof defaultValue === "string"
          ? defaultValue
          : "";
      return (
        <TextArea
          value={currentVal}
          onChange={(e) => onChange(e.target.value)}
          autoSize={{ minRows: 4, maxRows: 16 }}
          placeholder={hint || "请输入文本内容"}
          style={{
            fontFamily: SANS_MONO_FONT,
            fontSize: 12,
            lineHeight: 1.6,
          }}
        />
      );
    }

    // 6. 数值类型 InputNumber (int / float)
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
          step={type === "float" ? 0.1 : 1}
          precision={type === "float" ? 2 : 0}
          onChange={(v) => onChange(v ?? 0)}
          style={{ width: "100%", maxWidth: 240 }}
        />
      );
    }

    // 7. 字符串列表 (list / tags)
    if (type === "list") {
      const listVal: string[] = Array.isArray(value)
        ? (value as string[])
        : Array.isArray(defaultValue)
        ? (defaultValue as string[])
        : [];

      const handleRemoveTag = (removedTag: string) => {
        const nextList = listVal.filter((tag) => tag !== removedTag);
        onChange(nextList);
      };

      const handleAddTagConfirm = () => {
        if (newTagInput && !listVal.includes(newTagInput.trim())) {
          onChange([...listVal, newTagInput.trim()]);
        }
        setNewTagInput("");
        setIsAddingTag(false);
      };

      return (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 8px", alignItems: "center" }}>
          {listVal.map((tag) => (
            <Tag
              key={tag}
              closable
              onClose={() => handleRemoveTag(tag)}
              style={{
                margin: 0,
                fontSize: 12,
                padding: "2px 8px",
                borderRadius: 4,
                fontFamily: SANS_MONO_FONT,
              }}
            >
              {tag}
            </Tag>
          ))}
          {isAddingTag ? (
            <Input
              size="small"
              style={{ width: 140, fontFamily: SANS_MONO_FONT }}
              value={newTagInput}
              onChange={(e) => setNewTagInput(e.target.value)}
              onBlur={handleAddTagConfirm}
              onPressEnter={handleAddTagConfirm}
              autoFocus
            />
          ) : (
            <Tag
              onClick={() => setIsAddingTag(true)}
              style={{
                borderStyle: "dashed",
                cursor: "pointer",
                margin: 0,
                padding: "2px 8px",
                borderRadius: 4,
              }}
            >
              <PlusOutlined style={{ marginRight: 4 }} /> 添加条目
            </Tag>
          )}
        </div>
      );
    }

    // 7.1 文件 / 图片上传与列表 (file)
    if (type === "file") {
      const fileList: string[] = Array.isArray(value)
        ? (value as string[]).filter((x) => typeof x === "string" && x.trim().length > 0)
        : typeof value === "string" && value.trim().length > 0
        ? [value.trim()]
        : [];

      const handleRemoveFile = (indexToRemove: number) => {
        const nextList = fileList.filter((_, idx) => idx !== indexToRemove);
        onChange(Array.isArray(defaultValue) ? nextList : nextList[0] || "");
      };

      const handleAddFileUrl = () => {
        if (!newFileInput.trim()) return;
        const target = newFileInput.trim();
        const nextList = [...fileList, target];
        onChange(Array.isArray(defaultValue) ? nextList : target);
        setNewFileInput("");
        setIsAddingFile(false);
      };

      const handleUploadLocal = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        Array.from(files).forEach((file) => {
          const reader = new FileReader();
          reader.onload = (event) => {
            const dataUrl = event.target?.result as string;
            if (dataUrl) {
              const nextList = [...fileList, dataUrl];
              onChange(Array.isArray(defaultValue) ? nextList : dataUrl);
            }
          };
          reader.readAsDataURL(file);
        });

        e.target.value = "";
      };

      return (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
          {/* 文件/图片条目列表 */}
          {fileList.length > 0 ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
              {fileList.map((filePath, idx) => {
                const isImage =
                  filePath.startsWith("data:image/") ||
                  filePath.startsWith("http://") ||
                  filePath.startsWith("https://") ||
                  /\.(png|jpe?g|webp|gif|svg)$/i.test(filePath);

                let displayLabel = filePath;
                if (filePath.startsWith("data:image/")) {
                  const approxSize = Math.round((filePath.length * 3) / 4 / 1024);
                  displayLabel = `已上传图片 (${approxSize} KB)`;
                } else if (filePath.length > 35) {
                  displayLabel = `${filePath.slice(0, 18)}...${filePath.slice(-12)}`;
                }

                return (
                  <div
                    key={`${filePath}-${idx}`}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      background: token.colorFillAlter,
                      border: `1px solid ${token.colorBorderSecondary}`,
                      borderRadius: 6,
                      padding: "4px 8px 4px 6px",
                      boxShadow: "0 1px 2px rgba(0, 0, 0, 0.03)",
                      maxWidth: "100%",
                    }}
                  >
                    {/* 图片缩略图预览 (支持点击放大预览) */}
                    {isImage ? (
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: 4,
                          overflow: "hidden",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          background: isDark ? "#1e293b" : "#f1f5f9",
                          border: `1px solid ${token.colorBorderSecondary}`,
                          flexShrink: 0,
                        }}
                      >
                        <Image
                          src={filePath}
                          width={36}
                          height={36}
                          style={{
                            width: 36,
                            height: 36,
                            objectFit: "cover",
                            borderRadius: 4,
                            display: "block",
                          }}
                          fallback="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='36' height='36' viewBox='0 0 24 24' fill='none' stroke='%23888' stroke-width='2'><rect x='3' y='3' width='18' height='18' rx='2'/><circle cx='8.5' cy='8.5' r='1.5'/><polyline points='21 15 16 10 5 21'/></svg>"
                          preview={{
                            mask: <EyeOutlined style={{ fontSize: 13 }} />,
                          }}
                        />
                      </div>
                    ) : (
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: 4,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          background: token.colorFillSecondary,
                          flexShrink: 0,
                        }}
                      >
                        <FileOutlined style={{ color: token.colorTextSecondary, fontSize: 16 }} />
                      </div>
                    )}

                    <div style={{ display: "flex", flexDirection: "column", minWidth: 0, marginRight: 4 }}>
                      <span
                        style={{
                          fontSize: 12,
                          fontWeight: 500,
                          fontFamily: SANS_MONO_FONT,
                          color: token.colorText,
                          maxWidth: 220,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                        title={filePath}
                      >
                        {displayLabel}
                      </span>
                      {isImage && (
                        <span style={{ fontSize: 10, color: token.colorTextTertiary }}>
                          点击缩略图可全屏预览
                        </span>
                      )}
                    </div>

                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined style={{ fontSize: 11 }} />}
                      style={{ width: 22, height: 22, padding: 0 }}
                      onClick={() => handleRemoveFile(idx)}
                    />
                  </div>
                );
              })}
            </div>
          ) : (
            <div
              style={{
                padding: "8px 12px",
                background: token.colorFillAlter,
                border: `1px dashed ${token.colorBorderSecondary}`,
                borderRadius: 4,
                fontSize: 11,
                color: token.colorTextTertiary,
              }}
            >
              暂未添加参考图片或文件（支持上传本地图片、输入图片 URL 或相对路径）
            </div>
          )}

          {/* 添加控制栏 */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <input
              type="file"
              id={`file-upload-${fieldKey}`}
              multiple
              accept={
                Array.isArray(fieldSchema.file_types)
                  ? fieldSchema.file_types.map((ext) => `.${ext}`).join(",")
                  : "image/*"
              }
              style={{ display: "none" }}
              onChange={handleUploadLocal}
            />
            <Button
              size="small"
              icon={<UploadOutlined />}
              onClick={() => {
                document.getElementById(`file-upload-${fieldKey}`)?.click();
              }}
            >
              上传本地图片
            </Button>

            {isAddingFile ? (
              <Space.Compact style={{ maxWidth: 360 }}>
                <Input
                  size="small"
                  placeholder="输入 http:// 链接或本地相对路径"
                  value={newFileInput}
                  onChange={(e) => setNewFileInput(e.target.value)}
                  onPressEnter={handleAddFileUrl}
                  style={{ fontFamily: SANS_MONO_FONT, fontSize: 11 }}
                  autoFocus
                />
                <Button size="small" type="primary" onClick={handleAddFileUrl}>
                  确认
                </Button>
                <Button size="small" onClick={() => setIsAddingFile(false)}>
                  取消
                </Button>
              </Space.Compact>
            ) : (
              <Button
                size="small"
                type="dashed"
                icon={<PlusOutlined />}
                onClick={() => setIsAddingFile(true)}
              >
                添加图片 URL / 路径
              </Button>
            )}
          </div>
        </div>
      );
    }

    // 8. 普通单行字符串输入 (string)
    if (type === "string") {
      const currentVal =
        value !== undefined ? String(value) : String(defaultValue ?? "");
      return (
        <Input
          value={currentVal}
          onChange={(e) => onChange(e.target.value)}
          placeholder={hint || `请输入 ${title}`}
          allowClear
          style={{
            fontFamily:
              fieldKey.includes("id") ||
              fieldKey.includes("key") ||
              fieldKey.includes("url") ||
              fieldKey.includes("path")
                ? SANS_MONO_FONT
                : undefined,
          }}
        />
      );
    }

    // 9. 复杂对象兜底 (JSON 格式化输入)
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
        style={{ fontFamily: SANS_MONO_FONT, fontSize: 11 }}
      />
    );
  };

  const isDifferentFromDefault =
    defaultValue !== undefined &&
    JSON.stringify(value) !== JSON.stringify(defaultValue);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
        marginBottom: isSubField ? 8 : 12,
        padding: isSubField ? "8px 10px" : "12px 14px",
        background: isSubField ? "transparent" : token.colorBgContainer,
        border: isSubField
          ? `1px dashed ${token.colorBorderSecondary}`
          : `1px solid ${token.colorBorderSecondary}`,
        borderRadius: 6,
        boxShadow: isSubField ? "none" : "0 1px 2px rgba(0, 0, 0, 0.02)",
        width: "100%",
        boxSizing: "border-box",
      }}
    >
      {/* 头部标题与恢复默认控制 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          width: "100%",
        }}
      >
        <Space size={6} wrap style={{ flex: 1 }}>
          <Text
            strong
            style={{
              fontSize: isSubField ? 12 : 13,
              color: token.colorText,
              letterSpacing: "-0.2px",
            }}
          >
            {title}
          </Text>
          {!isSubField && (
            <span
              style={{
                fontSize: 11,
                fontFamily: SANS_MONO_FONT,
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

      {/* 核心控件区域 (Full Width) */}
      <div style={{ width: "100%", marginTop: 2 }}>{renderControl()}</div>

      {/* 底部详细说明文字：独立整行渲染，消除单字竖排与挤压变形 */}
      {hint && (
        <div
          style={{
            fontSize: 11,
            lineHeight: "1.5",
            color: token.colorTextSecondary,
            background: token.colorFillAlter,
            padding: "5px 8px",
            borderRadius: 4,
            marginTop: 4,
            wordBreak: "break-word",
          }}
        >
          {hint}
        </div>
      )}
    </div>
  );
};
