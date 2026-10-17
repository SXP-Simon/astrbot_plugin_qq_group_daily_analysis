import { useState, type CSSProperties } from "react";
import { Alert, Button, Card, Collapse, Empty, Form, Input, Modal, Popconfirm, Select, Space, Spin, Tag, Typography, theme } from "antd";
import { AppstoreOutlined, ArrowDownOutlined, ArrowUpOutlined, DeleteOutlined, EyeOutlined, ReloadOutlined, UndoOutlined } from "@ant-design/icons";
import { COMIC_ROTATION_MODES, DEFAULT_COMIC_TEMPLATE_CANDIDATES, comicTemplateOptions, type ComicRotationMode, type ComicRotationScope } from "../model/comicTemplateRotation";
import { comicPromptTemplates } from "../model/useComicPromptEditor";
import { useComicTemplateRotation } from "../model/useComicTemplateRotation";
import { ComicTemplateGallery } from "./ComicTemplateGallery";
import { ComicTemplatePreview } from "./ComicTemplatePreview";

interface ComicTemplateRotationSettingsProps {
  value: Record<string, unknown>;
  savedValue: Record<string, unknown>;
  dirty: boolean;
  disabled?: boolean;
  customPrompt: unknown;
  errors?: Record<string, string>;
  onPatch: (patch: Record<string, unknown>) => void;
  onOpenPromptSettings: () => void;
}

/** 每日漫画中的模板切换草稿、候选顺序和已保存进度。 */
export function ComicTemplateRotationSettings(props: ComicTemplateRotationSettingsProps) {
  const vm = useComicTemplateRotation(props);
  const { token } = theme.useToken();
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const template = comicPromptTemplates.find(({ id }) => id === previewId);
  const mode = COMIC_ROTATION_MODES.find(({ value }) => value === vm.settings.mode)!;
  const automatic = vm.settings.mode !== "fixed";
  const customEmpty = automatic && vm.settings.candidates.includes("custom") && (typeof props.customPrompt !== "string" || !props.customPrompt.trim());
  const poolError = props.errors?.comic_template_candidates ?? (automatic && vm.settings.candidates.length === 0 ? "自动切换至少需要一个候选模板。" : customEmpty ? "候选中包含自定义，请先在提示词设置中填写自定义漫画场景分析提示词。" : undefined);
  const candidateOptions = [...comicTemplateOptions, ...vm.settings.candidates.filter((id) => !comicTemplateOptions.some(({ value }) => id === value)).map((id) => ({ value: id, label: `未知模板：${id}` }))];
  const statusMode = COMIC_ROTATION_MODES.find(({ value }) => value === vm.status?.mode)?.label;
  const nextLabel = vm.status?.next_template_name ?? (vm.status?.mode === "random" ? "下次生成时随机决定" : vm.status?.mode === "daily_random" ? "当天首次生成时随机决定" : vm.status?.mode === "shuffle" ? "下次生成时洗牌决定" : "尚未确定");

  return <Card size="small" title="漫画模板自动切换" className="comic-rotation-settings" style={{ marginBottom: 16 }} styles={{ body: { display: "grid", gap: 18 } }}>
    <style>{`
      .comic-rotation-settings { container-type: inline-size; min-width: 0; }
      .comic-rotation-settings .ant-form-item { margin-bottom: 0; }
      .comic-rotation-settings .ant-select { width: 100%; min-width: 0; }
      .comic-rotation-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
      .comic-rotation-order { display: grid; gap: 8px; padding: 0; margin: 12px 0 0; list-style: none; }
      .comic-rotation-row { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px 12px; padding: 8px 12px; border: 1px solid var(--comic-rotation-border); border-radius: 8px; }
      .comic-rotation-row-name { display: flex; align-items: baseline; gap: 10px; min-width: 0; flex: 1 1 200px; overflow-wrap: anywhere; }
      .comic-rotation-actions { display: flex; flex-wrap: wrap; gap: 8px; }
      .comic-rotation-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
      .comic-rotation-summary > div { display: grid; gap: 4px; min-width: 0; overflow-wrap: anywhere; }
      .comic-rotation-manual { display: flex; flex-wrap: wrap; gap: 8px; }
      .comic-rotation-manual .ant-input { flex: 1 1 220px; min-width: 0; }
      @container (max-width: 540px) { .comic-rotation-fields, .comic-rotation-summary { grid-template-columns: minmax(0, 1fr); } .comic-rotation-row { padding: 10px; } .comic-rotation-actions { width: 100%; justify-content: flex-end; } }
    `}</style>
    <div className="comic-rotation-fields">
      <div id="cfg-field-daily_comic-comic_template_mode"><Form.Item label="切换模式" htmlFor="comic-template-mode" validateStatus={props.errors?.comic_template_mode ? "error" : undefined} help={props.errors?.comic_template_mode}>
        <Select id="comic-template-mode" disabled={props.disabled} value={vm.settings.mode} options={COMIC_ROTATION_MODES.map(({ value, label }) => ({ value, label }))} onChange={(next: ComicRotationMode) => props.onPatch({ comic_template_mode: next })} />
      </Form.Item></div>
      <div id="cfg-field-daily_comic-comic_template_scope"><Form.Item label="切换进度范围" htmlFor="comic-template-scope" validateStatus={props.errors?.comic_template_scope ? "error" : undefined} help={props.errors?.comic_template_scope} extra="自动模式生效。全局共享一套进度；按群独立时各自推进。">
        <Select id="comic-template-scope" disabled={props.disabled} value={vm.settings.scope} options={[{ value: "global", label: "全局共享" }, { value: "group", label: "按群独立" }]} onChange={(next: ComicRotationScope) => props.onPatch({ comic_template_scope: next })} />
      </Form.Item></div>
    </div>
    <Typography.Paragraph type="secondary" style={{ margin: 0 }}>{mode.description}{!automatic && <> <Button size="small" type="link" style={{ paddingInline: 0 }} onClick={props.onOpenPromptSettings}>前往默认漫画提示词设置</Button></>}</Typography.Paragraph>
    {(automatic || props.errors?.comic_template_candidates) && <div id="cfg-field-daily_comic-comic_template_candidates">
      <Form.Item label="候选模板" htmlFor="comic-template-candidates" validateStatus={poolError ? "error" : undefined} help={poolError ? <span role="alert" id="comic-template-candidates-error">{poolError}</span> : undefined} extra="按显示顺序轮换；随机模式也只会从这些模板中选择。自定义提示词需要手动加入。">
        <Select id="comic-template-candidates" mode="multiple" disabled={props.disabled} value={vm.settings.candidates} options={candidateOptions} optionFilterProp="label" virtual={false} onChange={vm.setCandidates} placeholder="选择参与切换的模板" aria-describedby={poolError ? "comic-template-candidates-error" : undefined} />
      </Form.Item>
      <Space wrap style={{ marginTop: 12 }}>
        <Button icon={<AppstoreOutlined />} onClick={() => setGalleryOpen(true)}>浏览模板画廊</Button>
        <Button disabled={props.disabled} onClick={() => vm.setCandidates([...DEFAULT_COMIC_TEMPLATE_CANDIDATES])}>选用全部内置模板</Button>
        <Button type="link" onClick={props.onOpenPromptSettings}>编辑自定义提示词</Button>
      </Space>
      {vm.settings.candidates.length > 0 ? <ol className="comic-rotation-order" aria-label="漫画模板候选顺序" style={{ "--comic-rotation-border": token.colorBorderSecondary } as CSSProperties}>
        {vm.settings.candidates.map((id, index) => {
          const label = candidateOptions.find(({ value }) => value === id)?.label ?? id;
          return <li className="comic-rotation-row" key={`${id}-${index}`}>
            <div className="comic-rotation-row-name"><Typography.Text type="secondary">{String(index + 1).padStart(2, "0")}</Typography.Text><Typography.Text strong>{label}</Typography.Text></div>
            <div className="comic-rotation-actions">
              <Button icon={<EyeOutlined />} aria-label={`预览${label}`} onClick={() => setPreviewId(id)}>预览</Button>
              <Button icon={<ArrowUpOutlined />} aria-label={`上移${label}`} disabled={props.disabled || index === 0} onClick={() => vm.moveCandidate(id, -1)} />
              <Button icon={<ArrowDownOutlined />} aria-label={`下移${label}`} disabled={props.disabled || index === vm.settings.candidates.length - 1} onClick={() => vm.moveCandidate(id, 1)} />
              <Button icon={<DeleteOutlined />} aria-label={`移除${label}`} disabled={props.disabled} onClick={() => vm.setCandidates(vm.settings.candidates.filter((candidate) => candidate !== id))} />
            </div>
          </li>;
        })}
      </ol> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未选择候选模板" />}
    </div>}
    <Collapse size="small" items={[{ key: "rules", label: "切换规则与角色提示词优先级", children: <Typography.Paragraph type="secondary" style={{ margin: 0, lineHeight: 1.8 }}>
      角色的专属漫画场景分析提示词优先；不为空时跳过模板切换，也不消耗切换进度。每个新任务开始时预留一次模板，失败也会占用该次顺序；内部重试、绘图服务降级不会重新抽取。预览和重发旧漫画不推进。每日模式使用服务器时区；每日顺序按日历推进，未生成的日期也会跳过。
      修改自动模式或候选集合、顺序后，下次生成使用新的进度；暂时切为固定模式会保留原来的轮换进度。
    </Typography.Paragraph> }]} />
    <div style={{ borderTop: `1px solid ${token.colorBorderSecondary}`, paddingTop: 16, display: "grid", gap: 12 }}>
      <Space wrap><Typography.Text strong>已保存的切换进度</Typography.Text><Tag color="blue">以服务器配置为准</Tag></Space>
      {props.dirty && <Alert type="warning" showIcon message="漫画配置有未保存修改" description="下方状态仍对应已保存的配置。保存后会刷新状态；重置进度暂不可用。" />}
      {vm.saved.scope === "group" && <>
        {vm.groupError && <Alert type="warning" showIcon message="群列表暂不可用，可填写完整会话标识" description={vm.groupError} />}
        <Form.Item label="查看群进度" htmlFor="comic-template-status-group">
          <div style={{ display: "flex", gap: 8 }}>
            <Select id="comic-template-status-group" value={vm.selectedUmo || undefined} disabled={props.disabled || vm.resetting} showSearch optionFilterProp="label" options={vm.options} loading={vm.groupLoading} onChange={vm.setSelectedUmo} placeholder="选择有历史记录的群" />
            <Button aria-label="刷新漫画群列表" icon={<ReloadOutlined />} disabled={props.disabled || vm.resetting} loading={vm.groupLoading} onClick={vm.refreshGroups} />
          </div>
        </Form.Item>
        <Collapse size="small" items={[{ key: "manual", label: "列表中没有目标群？填写群会话标识", children: <Form.Item label="完整群会话标识" htmlFor="comic-template-manual-group" validateStatus={vm.manualError ? "error" : undefined} help={vm.manualError} extra="在目标群发送 /sid 获取，例如 bot:GroupMessage:123456。">
          <div className="comic-rotation-manual"><Input id="comic-template-manual-group" value={vm.manualUmo} disabled={props.disabled || vm.resetting} onChange={(event) => vm.setManualUmo(event.target.value)} onPressEnter={(event) => { event.preventDefault(); vm.selectManual(); }} /><Button disabled={props.disabled || vm.resetting} onClick={vm.selectManual}>查看此群</Button></div>
        </Form.Item> }]} />
      </>}
      {vm.statusError && <Alert type="error" showIcon message="读取或重置进度失败" description={vm.statusError} action={<Button disabled={vm.resetting} onClick={vm.refresh}>重新读取状态</Button>} />}
      <Spin spinning={vm.statusLoading}>
        {vm.status ? <div className="comic-rotation-summary" aria-live="polite">
          <div><Typography.Text type="secondary">当前模板</Typography.Text><Typography.Text strong>{vm.status.current_template_name ?? "尚未生成"}</Typography.Text></div>
          <div><Typography.Text type="secondary">{vm.status.mode === "daily_sequential" ? "明日模板" : "下一次模板"}</Typography.Text><Typography.Text strong>{nextLabel}</Typography.Text></div>
          <div><Typography.Text type="secondary">模式 / 范围</Typography.Text><Typography.Text>{statusMode} · {vm.status.scope === "global" ? "全局共享" : vm.selectedUmo}</Typography.Text></div>
          <div><Typography.Text type="secondary">服务器日期</Typography.Text><Typography.Text>{vm.status.date}</Typography.Text></div>
        </div> : !vm.statusLoading && !vm.statusError && <Typography.Text type="secondary">{vm.saved.scope === "group" && !vm.selectedUmo ? "选择群后查看该群的已保存进度。" : "暂无切换进度。"}</Typography.Text>}
      </Spin>
      {vm.status?.warning && <Alert type="warning" showIcon message={vm.status.warning} />}
      <Space wrap>
        <Button icon={<ReloadOutlined />} loading={vm.statusLoading} disabled={props.disabled || vm.resetting || (vm.saved.scope === "group" && !vm.selectedUmo)} onClick={vm.refresh}>刷新进度</Button>
        <Popconfirm title="重置漫画模板切换进度？" description={vm.saved.scope === "group" ? "仅重置当前所选群。下次新任务从头轮换或重新抽取，当日模板也可能改变。" : "重置所有群共享的这套进度。下次新任务从头轮换或重新抽取，当日模板也可能改变。"} okText="重置进度" cancelText="保留" disabled={vm.resetLocked} onConfirm={vm.reset}>
          <Button icon={<UndoOutlined />} danger disabled={vm.resetLocked} loading={vm.resetting}>重置进度</Button>
        </Popconfirm>
      </Space>
    </div>
    <ComicTemplateGallery open={galleryOpen} onClose={() => setGalleryOpen(false)} onPreview={setPreviewId} selectedIds={vm.settings.candidates} onSelect={(id) => vm.setCandidates([...vm.settings.candidates, id])} multiple disabled={props.disabled} />
    <Modal title={`${template?.name ?? "自定义提示词"} · 风格示例`} open={previewId !== null} onCancel={() => setPreviewId(null)} footer={null} width={900} destroyOnHidden>
      {previewId !== null && <ComicTemplatePreview key={previewId} template={template} eager />}
      <Alert style={{ marginTop: 12 }} type="info" showIcon message="静态示例图仅供风格参考；查看和放大不会推进切换进度。" />
    </Modal>
  </Card>;
}
