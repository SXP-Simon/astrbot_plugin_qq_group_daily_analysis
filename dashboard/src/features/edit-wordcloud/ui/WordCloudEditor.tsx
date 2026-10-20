import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Alert, Button, Card, Col, Collapse, ColorPicker, Divider, Empty, Form, Image, Input, InputNumber, Modal, Popconfirm, Row, Select, Slider, Space, Spin, Switch, Tag, Typography, Upload, theme } from "antd";
import { DeleteOutlined, PictureOutlined, PlusOutlined, ReloadOutlined, UndoOutlined, UploadOutlined } from "@ant-design/icons";
import { useWordCloudEditor } from "../model/useWordCloudEditor";

const { Text, Paragraph } = Typography;

interface WordCloudEditorProps {
  value?: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
  onPatch: (patch: Record<string, unknown>) => void;
  scopeUmo?: string;
  protectedFonts?: string[];
  overrideKeys?: string[];
  disabled?: boolean;
}

function NumericSetting({ id, label, value, min, max, onChange, hint, error }: {
  id: string; label: string; value: number; min: number; max: number; onChange: (value: number) => void; hint?: string; error?: string;
}) {
  return <Form.Item label={label} htmlFor={id} extra={hint} validateStatus={error ? "error" : undefined} help={error}>
    <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
      <Slider ariaLabelForHandle={label} value={value} min={min} max={max} step={1} onChange={onChange} style={{ flex: 1, minWidth: 0 }} />
      <InputNumber id={id} aria-label={`${label}数值`} value={value} min={min} max={max} precision={0} onChange={(next) => { if (next !== null) onChange(next); }} style={{ width: 80 }} />
    </div>
  </Form.Item>;
}

export function WordCloudEditor({ value, onChange, onPatch, scopeUmo, protectedFonts = [], overrideKeys, disabled = false }: WordCloudEditorProps) {
  const vm = useWordCloudEditor(value, onChange, onPatch, scopeUmo, protectedFonts, overrideKeys, disabled);
  const { token } = theme.useToken();
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [imageOpen, setImageOpen] = useState(false);
  const [fontsOpen, setFontsOpen] = useState(false);
  const [renaming, setRenaming] = useState<{ id: string; label: string } | null>(null);
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(([entry]) => setContainerWidth(entry.contentRect.width));
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const options = vm.options;
  const previewWidth = vm.htmlPreview?.width ?? options.width;
  const previewHeight = vm.htmlPreview?.height ?? options.height;
  const scale = Math.min(1, containerWidth / previewWidth);
  const fieldState = (key: string) => ({ validateStatus: vm.fieldErrors[key] ? "error" as const : undefined, help: vm.fieldErrors[key] });
  const formStyle: CSSProperties = { marginBottom: 16 };
  const fontOptions = vm.catalog.fonts.map((font) => ({ value: font.id, label: font.label }));
  if (!fontOptions.some((font) => font.value === options.font)) fontOptions.push({ value: options.font, label: options.font === "wenkai" ? "霞鹜文楷" : options.font });
  const templateOptions = vm.catalog.templates.map((item) => ({ value: item.name, label: item.label }));
  if (!templateOptions.some((item) => item.value === options.template)) templateOptions.push({ value: options.template, label: `${options.template}（当前配置）` });
  const selectedTemplate = vm.catalog.templates.find((item) => item.name === options.template);

  return <div className="wordcloud-editor">
    {vm.messageContextHolder}
    <style>{`
      .wordcloud-editor-grid { display: grid; grid-template-columns: minmax(280px, 360px) minmax(0, 1fr); gap: 24px; align-items: start; }
      .wordcloud-preview { position: sticky; top: 0; min-width: 0; }
      .wordcloud-editor .ant-form-item { margin-bottom: 18px; }
      .wordcloud-editor .ant-collapse-content-box .ant-form-item:last-child { margin-bottom: 0; }
      @media (max-width: 900px) { .wordcloud-editor-grid { grid-template-columns: minmax(0, 1fr); gap: 16px; } .wordcloud-preview { position: static; } }
    `}</style>
    <Paragraph type="secondary" style={{ marginBottom: 20 }}>
      {scopeUmo ? "调整当前群的词云外观" : "调整全局默认样式"}，右侧自动预览当前草稿。预设和自动调整均可撤销；点击「保存配置」后应用于发送。
    </Paragraph>
    {(vm.validationError || vm.catalogError) && <Alert type="error" showIcon message={vm.validationError || vm.catalogError} action={<Button size="small" onClick={vm.refresh}>重试</Button>} style={{ marginBottom: 16 }} />}
    <div className="wordcloud-editor-grid">
      <Form layout="vertical" disabled={disabled} style={{ minWidth: 0 }}>
        <Card size="small" title="排版预设" style={formStyle}>
          <Space wrap>
            <Button onClick={() => vm.applyPreset("compact")}>紧凑</Button>
            <Button onClick={() => vm.applyPreset("balanced")}>均衡</Button>
            <Button onClick={() => vm.applyPreset("spacious")}>舒展</Button>
          </Space>
          <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 12, fontSize: 12 }}>联动调整字号、间距和词数，应用后仍可逐项微调。</Paragraph>
          <Space wrap>
            <Popconfirm title="恢复当前模板的默认外观？" description="只调整字体、排版与画布，发送和词频规则保持原值。" onConfirm={vm.restoreTemplate} disabled={!selectedTemplate?.defaults || disabled}>
              <Button disabled={!selectedTemplate?.defaults || disabled}>恢复模板默认</Button>
            </Popconfirm>
            {vm.undoLabel && <Button icon={<UndoOutlined />} onClick={vm.undo}>撤销{vm.undoLabel}</Button>}
          </Space>
        </Card>
        <Card size="small" title="生成与发送" style={formStyle}>
          <Form.Item label="启用词云" htmlFor="wc-enabled" {...fieldState("enabled")}>
            <Switch id="wc-enabled" checked={options.enabled} onChange={(next) => vm.update("enabled", next)} checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
          <Form.Item label="随群分析报告发送" htmlFor="wc-send" {...fieldState("send_with_report")} extra="关闭后仍可通过独立词云命令生成。词云在报告发送成功后发送。">
            <Switch id="wc-send" checked={options.send_with_report} onChange={(next) => vm.update("send_with_report", next)} checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
          <Form.Item label="词云模板" htmlFor="wc-template" {...fieldState("template")} style={{ marginBottom: 0 }} extra="仅列出提供词云布局的模板，与分析报告模板独立。">
            <Select id="wc-template" value={options.template} options={templateOptions} onChange={(next) => vm.update("template", next)} notFoundContent="暂无可用词云模板" />
          </Form.Item>
          {selectedTemplate?.thumbnail && <Image src={selectedTemplate.thumbnail} alt={`${selectedTemplate.label}模板缩略图`} width={140} style={{ marginTop: 12, borderRadius: 8 }} />}
        </Card>
        <Card size="small" title="字体与排版" style={formStyle}>
          <Form.Item label="字体" htmlFor="wc-font" {...fieldState("font")}>
            <Select id="wc-font" value={options.font} options={fontOptions} onChange={(next) => vm.update("font", next)} />
          </Form.Item>
          {vm.fontSample && <iframe title="所选字体样张" sandbox="allow-scripts" srcDoc={vm.fontSample} style={{ width: "100%", height: 86, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, marginBottom: 12, background: token.colorBgContainer }} />}
          {vm.fontSampleError && <Text type="secondary">{vm.fontSampleError}</Text>}
          <Space wrap>
          <Upload accept=".woff2,.woff,.ttf,.otf" showUploadList={false} beforeUpload={vm.uploadFont} disabled={vm.uploading || disabled}>
            <Button icon={<UploadOutlined />} loading={vm.uploading}>上传字体</Button>
          </Upload>
          <Button onClick={() => setFontsOpen(true)}>管理上传字体</Button>
          </Space>
          <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 20, fontSize: 12 }}>支持 WOFF2、WOFF、TTF、OTF，最多 20 MB。</Paragraph>
          <Row gutter={12}>
            <Col span={12}><Form.Item label="最小字号（px）" htmlFor="wc-min-font" {...fieldState("min_font_size")}>
              <InputNumber id="wc-min-font" value={options.min_font_size} min={12} max={160} precision={0} onChange={(next) => { if (next !== null) vm.update("min_font_size", next); }} style={{ width: "100%" }} />
            </Form.Item></Col>
            <Col span={12}><Form.Item label="最大字号（px）" htmlFor="wc-max-font" {...fieldState("max_font_size")}>
              <InputNumber id="wc-max-font" value={options.max_font_size} min={12} max={160} precision={0} onChange={(next) => { if (next !== null) vm.update("max_font_size", next); }} style={{ width: "100%" }} />
            </Form.Item></Col>
          </Row>
          <NumericSetting error={vm.fieldErrors.max_words} id="wc-max-words" label="最多展示词数" value={options.max_words} min={1} max={200} onChange={(next) => vm.update("max_words", next)} />
          <NumericSetting error={vm.fieldErrors.word_spacing} id="wc-word-spacing" label="词语间距（px）" value={options.word_spacing} min={0} max={40} onChange={(next) => vm.update("word_spacing", next)} hint="数值越小越紧凑；字号、间距和画布大小会影响实际排入数量。" />
          <Form.Item label="文字方向" htmlFor="wc-rotation" {...fieldState("rotation")} style={{ marginBottom: 0 }}>
            <Select id="wc-rotation" value={options.rotation} options={[{ value: "horizontal", label: "全横排" }, { value: "mixed", label: "横竖混排" }]} onChange={(next) => vm.update("rotation", next)} />
          </Form.Item>
        </Card>
        <Card size="small" title="画布与配色" style={formStyle}>
          <Row gutter={12}>
            <Col span={12}><Form.Item label="画布宽度（px）" htmlFor="wc-width" {...fieldState("width")}>
              <InputNumber id="wc-width" value={options.width} min={800} max={2400} step={100} precision={0} onChange={(next) => { if (next !== null) vm.update("width", next); }} style={{ width: "100%" }} />
            </Form.Item></Col>
            <Col span={12}><Form.Item label="画布高度（px）" htmlFor="wc-height" {...fieldState("height")}>
              <InputNumber id="wc-height" value={options.height} min={600} max={1800} step={100} precision={0} onChange={(next) => { if (next !== null) vm.update("height", next); }} style={{ width: "100%" }} />
            </Form.Item></Col>
          </Row>
          <Form.Item {...fieldState("palette")} label="词语颜色" extra={options.palette.length ? "自定义颜色最多 16 种；各颜色按词语分配。" : "当前跟随所选模板的默认配色。"} style={{ marginBottom: 0 }}>
            <Space wrap size={8}>
              {options.palette.map((color, index) => <Space.Compact key={index}>
                <ColorPicker value={color} disabledAlpha onChangeComplete={(next) => vm.update("palette", options.palette.map((item, itemIndex) => itemIndex === index ? next.toHexString() : item))}>
                  <Button aria-label={`编辑颜色 ${index + 1}：${color}`} style={{ padding: "0 8px" }}><span style={{ display: "inline-block", width: 18, height: 18, borderRadius: 4, background: color, border: `1px solid ${token.colorBorder}`, verticalAlign: "middle" }} /></Button>
                </ColorPicker>
                <Button aria-label={`删除颜色 ${index + 1}`} icon={<DeleteOutlined />} onClick={() => vm.update("palette", options.palette.filter((_, itemIndex) => itemIndex !== index))} />
              </Space.Compact>)}
              <Button icon={<PlusOutlined />} disabled={options.palette.length >= 16} onClick={() => vm.update("palette", [...options.palette, "#587785"])}>添加颜色</Button>
              {options.palette.length > 0 && <Button type="link" onClick={() => vm.update("palette", [])}>恢复模板配色</Button>}
            </Space>
          </Form.Item>
        </Card>
        <Collapse items={[{ key: "tokenizer", label: "词频与分词设置", children: <>
          <Form.Item label="词频权重" htmlFor="wc-weight" {...fieldState("weight_mode")} extra="按包含该词的消息数统计，可减少同一条消息中重复刷词的影响。">
            <Select id="wc-weight" value={options.weight_mode} options={[{ value: "message_count", label: "包含该词的消息数" }, { value: "occurrence_count", label: "词语总出现次数" }]} onChange={(next) => vm.update("weight_mode", next)} />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item label="最低词频" htmlFor="wc-frequency" {...fieldState("min_frequency")}><InputNumber id="wc-frequency" value={options.min_frequency} min={1} max={10000} precision={0} onChange={(next) => { if (next !== null) vm.update("min_frequency", next); }} style={{ width: "100%" }} /></Form.Item></Col>
            <Col span={12}><Form.Item label="最短词长" htmlFor="wc-length" {...fieldState("min_word_length")}><InputNumber id="wc-length" value={options.min_word_length} min={1} max={20} precision={0} onChange={(next) => { if (next !== null) vm.update("min_word_length", next); }} style={{ width: "100%" }} /></Form.Item></Col>
          </Row>
          <Form.Item label="额外停用词" htmlFor="wc-stopwords" {...fieldState("stopwords")} extra="这些词不会出现在词云中。输入后按回车，也可用逗号分隔。">
            <Select id="wc-stopwords" mode="tags" value={options.stopwords} tokenSeparators={[",", "，", "\n"]} onChange={(next: string[]) => vm.update("stopwords", next)} placeholder="输入要忽略的词" open={false} />
          </Form.Item>
          <Form.Item label="保留词 / 自定义词典" htmlFor="wc-keep-words" {...fieldState("keep_words")} extra="将昵称、作品名等作为完整词语识别。">
            <Select id="wc-keep-words" mode="tags" value={options.keep_words} tokenSeparators={[",", "，", "\n"]} onChange={(next: string[]) => vm.update("keep_words", next)} placeholder="输入需要完整保留的词" open={false} />
          </Form.Item>
        </> }]} />
      </Form>
      <div className="wordcloud-preview">
        <Card size="small" title={<Space wrap><span>词云预览</span><Tag>{vm.sourceId === "sample" ? "示例数据" : "群聊缓存"}</Tag></Space>} extra={<Button icon={<ReloadOutlined />} onClick={vm.refresh} disabled={disabled} aria-label="刷新词云预览" />}>
          <Form layout="vertical" disabled={disabled}>
            <Form.Item label="预览内容" htmlFor="wc-preview-source" style={{ marginBottom: 12 }}>
              <Select id="wc-preview-source" value={vm.sourceId} onChange={vm.setSourceId} style={{ width: "100%" }} options={[
                { value: "sample", label: "示例词频" },
                ...vm.snapshots.map((item) => ({ value: item.id, label: `${item.group_label} · ${item.date_str} · 最近一次词云` })),
              ]} />
            </Form.Item>
          </Form>
          {vm.snapshotError && <Alert type="warning" showIcon message={vm.snapshotError} action={<Button size="small" onClick={vm.refresh}>重试</Button>} style={{ marginBottom: 12 }} />}
          {vm.snapshotsLoaded && !vm.snapshotError && vm.snapshots.length === 0 && <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 12 }}>暂无群词云缓存，可先在群中生成一次词云，当前使用示例词频。</Paragraph>}
          {vm.sourceId !== "sample" && <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 12 }}>
            {vm.metadata ? `${vm.metadata.group_label} · ${vm.metadata.date_str} · ${vm.metadata.message_count} 条消息 · ${vm.metadata.eligible_word_count} 个有效词` : "正在读取缓存词频…"}
            <br />复用最近一次词云缓存，不重新拉取消息。可调整权重、最低词频和过滤规则；分词结果已固定，新增保留词无法重新组合原消息，需下次生成词云生效。
          </Paragraph>}
          <div role="status" aria-live="polite" aria-atomic="true" style={{ minHeight: 24, marginBottom: 12 }}>
            {vm.previewState === "loading" ? <Space><Spin size="small" /><Text type="secondary">{vm.htmlPreview ? "正在加载字体、图片并排版…" : "正在请求词云预览…"}</Text></Space> : vm.previewState === "ready" ? <Text type="secondary">排版已就绪{vm.counts ? ` · 已排入 ${vm.counts.placed} / ${vm.counts.total} 个词` : ""}</Text> : <Text type="danger">预览未完成</Text>}
          </div>
          {vm.previewError && <Alert type="error" showIcon message={vm.previewError} action={!vm.validationError && <Button size="small" disabled={disabled} onClick={vm.refresh}>重试预览</Button>} style={{ marginBottom: 12 }} />}
          {vm.previewState === "ready" && vm.counts && vm.counts.placed < vm.counts.total && <Alert type="info" showIcon message="部分词语未能排入画布，可缩小字号、间距或增大画布。" style={{ marginBottom: 12 }} />}
          <Space wrap style={{ marginBottom: 12 }}>
            <Button disabled={disabled || !!vm.validationError || vm.previewState !== "ready" || !vm.counts || vm.counts.placed >= vm.counts.total || !!vm.fitProgress} loading={!!vm.fitProgress} onClick={() => { void vm.fitMore(); }}>尝试容纳更多词</Button>
            {vm.fitProgress && <Button onClick={vm.cancelFit}>取消调整</Button>}
            {vm.undoLabel && <Button disabled={disabled} icon={<UndoOutlined />} onClick={vm.undo}>撤销调整</Button>}
          </Space>
          {(vm.fitProgress || vm.fitNotice) && <Paragraph aria-live="polite" type="secondary" style={{ marginBottom: 12 }}>{vm.fitProgress || vm.fitNotice}</Paragraph>}
          <div ref={containerRef} style={{ width: "100%", overflow: "hidden", background: token.colorFillQuaternary, borderRadius: 8, position: "relative", minHeight: 120 }}>
            {vm.htmlPreview ? <div style={{ height: previewHeight * scale, position: "relative", margin: "0 auto", width: previewWidth * scale }}>
              <iframe key={vm.htmlPreview.id} ref={vm.iframeRef} title="词云样式快速预览" sandbox="allow-scripts" srcDoc={vm.htmlPreview.html} style={{ width: previewWidth, height: previewHeight, border: 0, display: "block", transform: `scale(${scale})`, transformOrigin: "top left", ...(vm.previewState === "loading" ? { position: "fixed", top: 0, left: 0, opacity: 0, pointerEvents: "none", zIndex: -1 } as CSSProperties : {}) }} />
            </div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={vm.validationError ? "请先修正标红字段，原输入已保留" : vm.previewState === "error" ? "预览加载失败，请点击重试预览" : "正在准备词云预览"} style={{ padding: 32 }} />}
          </div>
          <Divider style={{ margin: "16px 0" }} />
          <Space wrap style={{ justifyContent: "space-between", width: "100%" }}>
            <Text type="secondary">{options.width} × {options.height} px · 固定画布</Text>
            <Button icon={<PictureOutlined />} loading={vm.imageLoading} disabled={disabled || !!vm.validationError || !!vm.fitProgress} onClick={() => { void vm.renderImage(); }}>生成 T2I 实际图片</Button>
          </Space>
          <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>快速预览与发送图片使用同一模板。实际图片预览会通过 AstrBot 渲染当前草稿，无需先保存。</Paragraph>
          {vm.imageError && <Alert type="error" showIcon message={vm.imageError} style={{ marginTop: 12 }} />}
          {vm.image && <div style={{ marginTop: 16 }}>
            <Text strong>当前草稿的 T2I 图片</Text>
            <Image src={vm.image} alt="当前词云草稿的 T2I 实际渲染图片" width="100%" style={{ marginTop: 8, borderRadius: 8 }} preview={{ visible: imageOpen, onVisibleChange: setImageOpen }} />
          </div>}
        </Card>
      </div>
    </div>
    <Modal title="管理上传字体" open={fontsOpen} onCancel={() => setFontsOpen(false)} footer={<Button onClick={() => setFontsOpen(false)}>完成</Button>}>
      <Paragraph type="secondary">重命名立即生效。正在被已保存配置或当前草稿使用的字体不能删除；删除后保留回收存档。</Paragraph>
      {vm.catalog.fonts.filter((font) => font.uploaded || font.id.startsWith("uploaded:")).length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="还没有上传字体" />}
      {vm.catalog.fonts.filter((font) => font.uploaded || font.id.startsWith("uploaded:")).map((font) => <div key={font.id} style={{ padding: "12px 0", borderBottom: `1px solid ${token.colorBorderSecondary}` }}>
        <Space wrap style={{ display: "flex", justifyContent: "space-between" }}>
          <Text style={{ overflowWrap: "anywhere", minWidth: 0 }}>{font.label}{font.id === options.font && <Tag style={{ marginLeft: 8 }}>当前字体</Tag>}</Text>
          <Space>
            <Button size="small" disabled={disabled || vm.fontBusy} onClick={() => setRenaming({ id: font.id, label: font.label })}>重命名</Button>
            <Popconfirm title="将此字体移入回收存档？" description="可以撤销最近一次删除。" onConfirm={() => vm.deleteFont(font.id)}>
              <Button size="small" danger disabled={disabled || vm.fontBusy || font.id === options.font || protectedFonts.includes(font.id)}>删除</Button>
            </Popconfirm>
          </Space>
        </Space>
      </div>)}
      {vm.deletedFont && <Button style={{ marginTop: 16 }} icon={<UndoOutlined />} disabled={disabled} loading={vm.fontBusy} onClick={() => { void vm.restoreFont(); }}>撤销最近一次删除</Button>}
    </Modal>
    <Modal title="重命名字体" open={!!renaming} confirmLoading={vm.fontBusy} onCancel={() => setRenaming(null)} onOk={() => { if (renaming) void vm.renameFont(renaming.id, renaming.label).then((success) => { if (success) setRenaming(null); }); }} okButtonProps={{ disabled }}>
      <Form layout="vertical"><Form.Item label="字体名称" htmlFor="wc-font-name"><Input id="wc-font-name" maxLength={80} value={renaming?.label ?? ""} onChange={(event) => setRenaming((current) => current ? { ...current, label: event.target.value } : null)} /></Form.Item></Form>
    </Modal>
  </div>;
}
