import type { ReactNode } from "react";
import { Alert, Button, Collapse, ColorPicker, Empty, Form, Input, InputNumber, Popconfirm, Select, Space, Switch, Tag, Typography, theme } from "antd";
import { DeleteOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { useWordCloudGroupOverrides, type WordCloudGroupOverridesProps } from "../model/useWordCloudGroupOverrides";
import { isGroupUmo, WORDCLOUD_OVERRIDE_FIELDS, type WordCloudOverrideField } from "../model/wordCloudGroupOverrides";

const NUMBERS: Partial<Record<WordCloudOverrideField, { min: number; max: number; unit: string }>> = {
  min_font_size: { min: 12, max: 160, unit: "px" },
  max_font_size: { min: 12, max: 160, unit: "px" },
  max_words: { min: 1, max: 200, unit: "个" },
  word_spacing: { min: 0, max: 40, unit: "px" },
  width: { min: 800, max: 2400, unit: "px" },
  height: { min: 600, max: 1800, unit: "px" },
  min_frequency: { min: 1, max: 10000, unit: "次" },
  min_word_length: { min: 1, max: 20, unit: "字" },
};

const ENUM_OPTIONS = {
  rotation: [{ value: "horizontal", label: "全部横排" }, { value: "mixed", label: "横竖混排" }],
  weight_mode: [{ value: "message_count", label: "包含该词的消息数" }, { value: "occurrence_count", label: "词语总出现次数" }],
};

export function WordCloudGroupOverrides(props: WordCloudGroupOverridesProps) {
  const vm = useWordCloudGroupOverrides(props);
  const { token } = theme.useToken();
  const labels = WORDCLOUD_OVERRIDE_FIELDS.map(({ key, label }) => ({ value: key, label }));
  const inherited = WORDCLOUD_OVERRIDE_FIELDS.filter(({ key }) => !vm.selectedKeys.includes(key));

  const renderField = ({ key, label }: typeof WORDCLOUD_OVERRIDE_FIELDS[number]) => {
    const value = vm.effective[key];
    const id = `wordcloud-group-${key}`;
    const range = NUMBERS[key];
    const accessibility = { "aria-invalid": Boolean(vm.errors[key]), "aria-describedby": vm.errors[key] ? `${id}-error` : undefined };
    let control: ReactNode;
    if (key === "enabled" || key === "send_with_report") {
      control = <Switch id={id} {...accessibility} disabled={vm.locked} checked={value === true} checkedChildren="开启" unCheckedChildren="关闭" onChange={(next) => vm.update(key, next)} />;
    } else if (key === "template" || key === "font") {
      control = <Select id={id} {...accessibility} disabled={vm.locked} value={typeof value === "string" ? value : undefined} loading={vm.catalog.loading} options={key === "template" ? vm.catalog.templateOptions : vm.catalog.fontOptions} showSearch optionFilterProp="label" onChange={(next: string) => vm.update(key, next)} />;
    } else if (range) {
      control = <InputNumber id={id} {...accessibility} disabled={vm.locked} value={typeof value === "number" ? value : null} min={range.min} max={range.max} precision={0} style={{ width: "100%" }} onChange={(next) => { if (next !== null) vm.update(key, next); }} />;
    } else if (key === "rotation" || key === "weight_mode") {
      control = <Select id={id} {...accessibility} disabled={vm.locked} value={typeof value === "string" ? value : undefined} options={ENUM_OPTIONS[key]} onChange={(next: string) => vm.update(key, next)} />;
    } else if (key === "palette") {
      const colors = Array.isArray(value) ? value.filter((color): color is string => typeof color === "string") : [];
      control = <div id={id} role="group" aria-label="本群词语配色" {...accessibility}><Space wrap size={8}>
        {colors.map((color, index) => <Space.Compact key={index}>
          <ColorPicker disabled={vm.locked} value={/^#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?$/.test(color) ? color : undefined} disabledAlpha onChangeComplete={(next) => vm.update(key, colors.map((item, i) => i === index ? next.toHexString() : item))}>
            <Button disabled={vm.locked} aria-label={`编辑本群颜色 ${index + 1}：${color}`} style={{ paddingInline: 8 }}><span style={{ display: "inline-block", width: 18, height: 18, borderRadius: 4, background: color, border: `1px solid ${token.colorBorder}` }} /></Button>
          </ColorPicker>
          <Button disabled={vm.locked} aria-label={`删除本群颜色 ${index + 1}`} icon={<DeleteOutlined />} onClick={() => vm.update(key, colors.filter((_, i) => i !== index))} />
        </Space.Compact>)}
        <Button icon={<PlusOutlined />} disabled={vm.locked || colors.length >= 16} onClick={() => vm.update(key, [...colors, "#587785"])}>添加颜色</Button>
        {colors.length > 0 ? <Button disabled={vm.locked} type="link" onClick={() => vm.update(key, [])}>使用模板配色</Button> : <Typography.Text type="secondary">使用本群所选模板的配色</Typography.Text>}
      </Space></div>;
    } else {
      control = <Select id={id} {...accessibility} mode="tags" disabled={vm.locked} value={Array.isArray(value) ? value : []} tokenSeparators={[",", "，", "\n"]} open={false} placeholder="输入词语后按回车" onChange={(next: string[]) => vm.update(key, next)} />;
    }
    return <div key={key} className={key === "palette" ? "wc-overrides-wide" : undefined}>
      <Form.Item label={<Space size={6} wrap><span>{label}{range ? `（${range.unit}）` : ""}</span><Tag color="blue" style={{ margin: 0 }}>本群自定义</Tag></Space>} htmlFor={id} validateStatus={vm.errors[key] ? "error" : undefined} help={vm.errors[key] ? <span role="alert" id={`${id}-error`}>{vm.errors[key]}</span> : undefined}>
        {control}
      </Form.Item>
      <Button type="link" size="small" disabled={vm.locked} style={{ paddingInline: 0, marginTop: 4 }} onClick={() => vm.setFields(vm.selectedKeys.filter((item) => item !== key))}>恢复继承</Button>
    </div>;
  };

  return <div className="wordcloud-group-overrides">
    <style>{`
      .wordcloud-group-overrides { container-type: inline-size; min-width: 0; }
      .wc-overrides-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 24px; }
      .wc-overrides-wide { grid-column: 1 / -1; }
      .wordcloud-group-overrides .ant-select { width: 100%; }
      .wordcloud-group-overrides .ant-form-item { margin-bottom: 0; }
      .wc-overrides-manual { display: flex; gap: 8px; min-width: 0; }
      .wc-overrides-manual .ant-input { min-width: 0; }
      .wc-overrides-inherited { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--wc-border); }
      @container (max-width: 540px) { .wc-overrides-grid { grid-template-columns: minmax(0, 1fr); } .wc-overrides-manual { flex-wrap: wrap; } .wc-overrides-manual > button { width: 100%; } }
    `}</style>
    <Typography.Paragraph type="secondary">先选择群，再勾选需要单独设置的项目。其他项目实时继承上方全局草稿，保存配置后生效。</Typography.Paragraph>
    {vm.malformed && <Alert type="error" showIcon message="群级覆盖格式有误，请在下方 JSON 高级设置中修复；原内容已保留。" style={{ marginBottom: 16 }} />}
    {vm.loadError && <Alert type="warning" showIcon message="群列表加载失败，仍可编辑已有群或手动填写会话标识" description={vm.loadError} action={<Button size="small" onClick={vm.refresh}>重试</Button>} style={{ marginBottom: 16 }} />}
    <Form.Item label="选择群" htmlFor="wordcloud-group-selector" style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", gap: 8 }}>
        <Select id="wordcloud-group-selector" disabled={props.disabled || vm.malformed} showSearch optionFilterProp="label" value={vm.selected || undefined} loading={vm.loading} options={vm.options} onChange={vm.setSelected} placeholder="选择有历史记录的群或已有覆盖" style={{ minWidth: 0, flex: 1 }} />
        <Button aria-label="刷新词云群列表" disabled={props.disabled} icon={<ReloadOutlined />} loading={vm.loading} onClick={vm.refresh} />
      </div>
    </Form.Item>
    <Collapse size="small" style={{ marginBottom: 16 }} items={[{ key: "manual", label: "列表中没有目标群？填写完整会话标识", children: <Form.Item label="群会话标识" htmlFor="wordcloud-group-manual" validateStatus={vm.manualError ? "error" : undefined} help={vm.manualError} extra="在目标群发送 /sid 获取，例如 bot:GroupMessage:123456。">
      <div className="wc-overrides-manual"><Input id="wordcloud-group-manual" value={vm.manualUmo} disabled={props.disabled || vm.malformed} onChange={(event) => vm.setManualUmo(event.target.value)} onPressEnter={(event) => { event.preventDefault(); vm.selectManual(); }} placeholder="平台 ID:GroupMessage:群号" /><Button disabled={props.disabled || vm.malformed} onClick={vm.selectManual}>选择此群</Button></div>
    </Form.Item> }]} />
    {!vm.selected ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选择群后设置覆盖；当前配置保持不变" /> : <>
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, overflowWrap: "anywhere", marginBottom: 16 }}>{vm.selected}</Typography.Paragraph>
      {props.onEditAppearance && <Button type="primary" disabled={vm.locked || !isGroupUmo(vm.selected)} onClick={() => props.onEditAppearance?.(vm.selected)} style={{ marginBottom: 16 }}>编辑本群外观并预览</Button>}
      {vm.invalidGroup && <Alert type="error" showIcon message="此群覆盖内容必须是对象，请通过下方 JSON 高级设置修复；原内容已保留。" style={{ marginBottom: 16 }} />}
      {vm.catalog.error && <Alert type="warning" showIcon message="模板与字体目录暂不可用，当前配置已保留" description={vm.catalog.error} action={<Button size="small" onClick={vm.catalog.refresh}>重试</Button>} style={{ marginBottom: 16 }} />}
      <Form.Item label="本群需要覆盖的项目" htmlFor="wordcloud-group-fields" extra="取消选择即恢复继承；新增项目以当前全局值为起点。" style={{ marginBottom: 16 }}>
        <Select id="wordcloud-group-fields" mode="multiple" disabled={vm.locked} options={labels} value={vm.selectedKeys} onChange={vm.setFields} optionFilterProp="label" placeholder="全部继承全局默认" />
      </Form.Item>
      {vm.selectedKeys.length > 0 && <div className="wc-overrides-grid" style={{ marginBlock: 20 }}>{WORDCLOUD_OVERRIDE_FIELDS.filter(({ key }) => vm.selectedKeys.includes(key)).map(renderField)}</div>}
      {Object.entries(vm.errors).some(([key]) => !vm.selectedKeys.includes(key as WordCloudOverrideField)) && <Alert type="warning" showIcon message="继承的全局设置有校验错误，请先修复上方全局配置。" style={{ marginBottom: 16 }} />}
      <Space wrap style={{ marginBottom: inherited.length ? 16 : 0 }}>
        <Tag color={vm.selectedKeys.length ? "blue" : "default"}>{vm.selectedKeys.length ? `已覆盖 ${vm.selectedKeys.length} 项` : "全部继承全局"}</Tag>
        <Popconfirm title="将本群已覆盖项目恢复为全局默认？" description="其他群不受影响；保存配置后生效。" okText="恢复继承" cancelText="保留" onConfirm={() => vm.setFields([])}>
          <Button disabled={vm.locked || !vm.selectedKeys.length}>本群全部恢复继承</Button>
        </Popconfirm>
      </Space>
      {inherited.length > 0 && <Collapse size="small" items={[{ key: "inherited", label: `查看继承的全局设置（${inherited.length} 项）`, children: inherited.map(({ key, label }) => {
        const value = vm.effective[key];
        const optionLabel = key === "template" ? vm.catalog.templateOptions.find((option) => option.value === value)?.label : key === "font" ? vm.catalog.fontOptions.find((option) => option.value === value)?.label : key === "rotation" || key === "weight_mode" ? ENUM_OPTIONS[key].find((option) => option.value === value)?.label : undefined;
        const display = optionLabel ?? (typeof value === "boolean" ? value ? "开启" : "关闭" : Array.isArray(value) ? value.length ? value.join("、") : key === "palette" ? "模板默认配色" : "未设置" : String(value));
        return <div key={key} className="wc-overrides-inherited" style={{ borderColor: token.colorBorderSecondary }}><Typography.Text>{label}</Typography.Text><Typography.Text type="secondary" style={{ textAlign: "right", overflowWrap: "anywhere", maxWidth: "65%" }}>{display}</Typography.Text></div>;
      }) }]} />}
    </>}
  </div>;
}
