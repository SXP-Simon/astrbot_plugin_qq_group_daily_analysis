import { useEffect, useState, type ReactNode } from "react";
import { Alert, Button, Card, Collapse, ColorPicker, Form, Input, InputNumber, Popconfirm, Select, Space, Switch, Typography, theme } from "antd";
import { DeleteOutlined, FontSizeOutlined, PlusOutlined, UndoOutlined } from "@ant-design/icons";
import type { SchemaFieldItem } from "../../../entities/config/model/types";
import { useWordCloudCatalog } from "../../../features/edit-wordcloud/model/useWordCloudCatalog";
import { FieldRenderer } from "../../../widgets/config-form/ui/FieldRenderer";
import { WordCloudGroupOverrides } from "../../../features/edit-wordcloud/ui/WordCloudGroupOverrides";

interface WordCloudSettingsProps {
  fields: { key: string; schema: SchemaFieldItem; value: unknown }[];
  value?: Record<string, unknown>;
  errors?: Record<string, string>;
  disabled: boolean;
  editorOpen: boolean;
  catalogRevision: number;
  searching: boolean;
  dirty: boolean;
  onRestoreSaved: () => void;
  onEditGroupAppearance: (umo: string) => void;
  onChange: (key: string, value: unknown) => void;
  onOpenEditor: () => void;
}

const SECTIONS = [
  { title: "生成与发送", keys: ["enabled", "send_with_report"] },
  { title: "外观与排版", keys: ["template", "font", "min_font_size", "max_font_size", "max_words", "word_spacing", "width", "height", "rotation", "palette"] },
  { title: "词频规则", keys: ["weight_mode", "min_frequency", "min_word_length", "stopwords", "keep_words"] },
];
const NUMBERS: Record<string, { min: number; max: number; unit: string }> = {
  min_font_size: { min: 12, max: 160, unit: "px" },
  max_font_size: { min: 12, max: 160, unit: "px" },
  max_words: { min: 1, max: 200, unit: "个" },
  word_spacing: { min: 0, max: 40, unit: "px" },
  width: { min: 800, max: 2400, unit: "px" },
  height: { min: 600, max: 1800, unit: "px" },
  min_frequency: { min: 1, max: 10000, unit: "次" },
  min_word_length: { min: 1, max: 20, unit: "字" },
};
const HINTS: Record<string, string> = {
  enabled: "开启后可使用 /群词云 独立生成词云。",
  send_with_report: "报告发送成功后附送；关闭后仍可独立生成。",
  template: "与群分析报告的模板独立设置。",
  font: "已上传字体也可选择；新字体可在外观编辑器中上传。",
  max_words: "实际展示数量取决于有效词频和画布空间。",
  word_spacing: "数值越小，词语排列越紧密。",
  weight_mode: "按消息数统计，可减少单条消息中重复刷词的影响。",
  stopwords: "这些词不会出现在词云中；输入后按回车或逗号添加。",
  keep_words: "将昵称、作品名等作为完整词语识别。",
};

export function WordCloudSettings({ fields, value = {}, errors = {}, disabled, editorOpen, catalogRevision, searching, dirty, onRestoreSaved, onEditGroupAppearance, onChange, onOpenEditor }: WordCloudSettingsProps) {
  const { token } = theme.useToken();
  const catalog = useWordCloudCatalog({ active: !disabled && !editorOpen, template: typeof value.template === "string" ? value.template : "ATRI", font: typeof value.font === "string" ? value.font : "wenkai", revision: catalogRevision });
  const [advancedOpen, setAdvancedOpen] = useState<string[]>([]);
  const knownKeys = SECTIONS.flatMap((section) => section.keys);
  const advancedFields = fields.filter((field) => !knownKeys.includes(field.key));
  const revealAdvanced = advancedFields.some((field) => Boolean(errors[field.key]) || searching);
  useEffect(() => {
    if (revealAdvanced) setAdvancedOpen(["advanced"]);
  }, [revealAdvanced]);

  const renderField = (field: WordCloudSettingsProps["fields"][number]) => {
    const { key, schema, value: current } = field;
    const id = `wordcloud-setting-${key}`;
    const label = `${schema.description || key}${NUMBERS[key] ? `（${NUMBERS[key].unit}）` : ""}`;
    const hint = HINTS[key];
    const accessibility = { "aria-invalid": Boolean(errors[key]), "aria-describedby": errors[key] ? `${id}-error` : undefined };
    let control: ReactNode;
    if (key === "enabled" || key === "send_with_report") {
      control = <Switch id={id} {...accessibility} checked={current === true} onChange={(next) => onChange(key, next)} checkedChildren="开启" unCheckedChildren="关闭" />;
    } else if (key === "template" || key === "font") {
      control = <Select id={id} {...accessibility} value={typeof current === "string" ? current : undefined} loading={catalog.loading} showSearch optionFilterProp="label" options={key === "template" ? catalog.templateOptions : catalog.fontOptions} onChange={(next: string) => onChange(key, next)} notFoundContent={catalog.loading ? "正在加载…" : "暂无可用选项"} />;
    } else if (NUMBERS[key]) {
      const range = NUMBERS[key];
      control = <InputNumber id={id} {...accessibility} value={typeof current === "number" ? current : null} min={key === "max_font_size" && typeof value.min_font_size === "number" ? value.min_font_size : range.min} max={key === "min_font_size" && typeof value.max_font_size === "number" ? value.max_font_size : range.max} precision={0} onChange={(next) => { if (next !== null) onChange(key, next); }} style={{ width: "100%" }} />;
    } else if (key === "rotation" || key === "weight_mode") {
      const options = key === "rotation" ? [{ value: "horizontal", label: "全部横排" }, { value: "mixed", label: "横竖混排" }] : [{ value: "message_count", label: "包含该词的消息数" }, { value: "occurrence_count", label: "词语总出现次数" }];
      control = <Select id={id} {...accessibility} value={typeof current === "string" ? current : undefined} options={options} onChange={(next: string) => onChange(key, next)} />;
    } else if (key === "palette") {
      const colors = Array.isArray(current) ? current.filter((color): color is string => typeof color === "string") : [];
      control = <div id={id} {...accessibility} role="group" aria-label={label}>
        <Space wrap size={8}>
          {colors.map((color, index) => <Space.Compact key={index}>
            <ColorPicker value={color} disabledAlpha onChangeComplete={(next) => onChange(key, colors.map((item, i) => i === index ? next.toHexString() : item))}>
              <Button aria-label={`编辑词云颜色 ${index + 1}`} style={{ paddingInline: 8 }}><span style={{ display: "inline-block", width: 18, height: 18, borderRadius: 4, background: color, border: `1px solid ${token.colorBorder}` }} /></Button>
            </ColorPicker>
            <Button aria-label={`删除词云颜色 ${index + 1}`} icon={<DeleteOutlined />} onClick={() => onChange(key, colors.filter((_, i) => i !== index))} />
          </Space.Compact>)}
          <Button icon={<PlusOutlined />} disabled={disabled || colors.length >= 16} onClick={() => onChange(key, [...colors, "#587785"])}>添加颜色</Button>
          {colors.length > 0 ? <Button type="link" disabled={disabled} onClick={() => onChange(key, [])}>恢复模板配色</Button> : <Typography.Text type="secondary">跟随模板默认配色</Typography.Text>}
        </Space>
      </div>;
    } else {
      control = <Select id={id} {...accessibility} mode="tags" value={Array.isArray(current) ? current : []} tokenSeparators={[",", "，", "\n"]} onChange={(next: string[]) => onChange(key, next)} open={false} placeholder={key === "stopwords" ? "输入要忽略的词" : "输入需要完整识别的词"} />;
    }
    const wide = ["palette", "weight_mode"].includes(key);
    return <div key={key} id={`cfg-field-wordcloud-${key}`} className={wide ? "wc-settings-wide" : undefined}>
      <Form.Item label={label} htmlFor={id} extra={hint} validateStatus={errors[key] ? "error" : undefined} help={errors[key] ? <span role="alert" id={`${id}-error`}>{errors[key]}</span> : undefined}>
        {control}
      </Form.Item>
    </div>;
  };

  return <div className="wordcloud-settings">
    <style>{`
      .wordcloud-settings { container-type: inline-size; min-width: 0; }
      .wc-settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px 24px; }
      .wordcloud-settings .ant-form-item { margin-bottom: 0; min-width: 0; }
      .wordcloud-settings .ant-form-item-label { padding-bottom: 6px; }
      .wordcloud-settings .ant-form-item-extra { margin-top: 5px; min-height: 0; font-size: 12px; }
      .wordcloud-settings .ant-select { width: 100%; }
      .wc-settings-wide { grid-column: 1 / -1; }
      .wc-settings-intro { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
      @container (max-width: 540px) { .wc-settings-grid { grid-template-columns: minmax(0, 1fr); gap: 16px; } .wc-settings-actions, .wc-settings-actions .ant-space-item, .wc-settings-actions button { width: 100%; } }
      @media (max-width: 767px) { .wordcloud-settings .ant-select-single { height: 44px; } .wordcloud-settings .ant-input-number-input { height: 42px; } .wordcloud-settings .ant-btn { min-height: 40px; } }
    `}</style>
    <div className="wc-settings-intro" style={{ padding: 16, marginBottom: 16, borderRadius: token.borderRadiusLG, background: token.colorFillAlter }}>
      <div><Typography.Text strong>全局默认词云</Typography.Text><div style={{ color: token.colorTextSecondary, fontSize: 12, marginTop: 4 }}>调整下方设置后保存生效；打开编辑器可边调整边预览。</div></div>
      <Space wrap className="wc-settings-actions">
        <Popconfirm title="恢复词云上次保存的设置？" description="词云全局设置和群级覆盖将恢复，其他分组草稿会保留。" okText="恢复" cancelText="取消" onConfirm={onRestoreSaved} disabled={!dirty || disabled}>
          <Button icon={<UndoOutlined />} disabled={!dirty || disabled}>撤销词云修改</Button>
        </Popconfirm>
        <Button type="primary" icon={<FontSizeOutlined />} onClick={onOpenEditor} disabled={disabled}>外观编辑与预览</Button>
      </Space>
    </div>
    {catalog.error && <Alert type="warning" showIcon message="模板与字体列表加载失败" description={catalog.error} action={<Button size="small" onClick={catalog.refresh}>重试</Button>} style={{ marginBottom: 16 }} />}
    <Form component={false} layout="vertical" disabled={disabled}>
      {SECTIONS.map((section) => {
        const visible = section.keys.flatMap((key) => fields.filter((field) => field.key === key));
        return visible.length > 0 && <Card key={section.title} size="small" title={section.title} style={{ marginBottom: 16 }} styles={{ body: { padding: 20 } }}>
          <div className="wc-settings-grid">{visible.map(renderField)}</div>
        </Card>;
      })}
    {advancedFields.length > 0 && <Collapse activeKey={advancedOpen} onChange={(next) => setAdvancedOpen(Array.isArray(next) ? next : [next])} items={[{ key: "advanced", label: "群级覆盖与高级设置", children: <>
      <Typography.Paragraph type="secondary">为指定群设置单独参数，未覆盖的项目沿用上方全局默认值。</Typography.Paragraph>
      {advancedFields.map((field) => field.key === "group_overrides" ? <div key={field.key} id="cfg-field-wordcloud-group_overrides">
        {errors.group_overrides && <Alert type="error" message={errors.group_overrides} showIcon style={{ marginBottom: 12 }} />}
        <WordCloudGroupOverrides value={field.value} globalValue={value} disabled={disabled} active={advancedOpen.includes("advanced")} catalogRevision={catalogRevision} onEditAppearance={onEditGroupAppearance} onChange={(next) => onChange("group_overrides", next)} />
        <Collapse style={{ marginTop: 16 }} items={[{ key: "json", label: "JSON 高级编辑", children: <>
          <Typography.Paragraph type="secondary">可用于修复旧数据或编辑扩展字段。通常使用上方可视化设置即可。</Typography.Paragraph>
          <Input.TextArea aria-label="群级覆盖 JSON" disabled={disabled} value={typeof field.value === "string" ? field.value : JSON.stringify(field.value === undefined ? {} : field.value, null, 2)} autoSize={{ minRows: 4, maxRows: 16 }} status={errors.group_overrides ? "error" : undefined} onChange={(event) => {
            const draft = event.target.value;
            try { onChange("group_overrides", JSON.parse(draft) as unknown); }
            catch { onChange("group_overrides", draft); }
          }} style={{ fontFamily: "monospace" }} />
        </> }]} />
      </div> : <FieldRenderer key={field.key} fieldKey={field.key} fieldSchema={field.schema} value={field.value} fullKeyPath={`wordcloud.${field.key}`} error={errors[field.key]} subErrors={errors} onChange={(next) => { if (!disabled) onChange(field.key, next); }} />)}
    </> }]} />}
    </Form>
  </div>;
}
