import type { Dispatch, SetStateAction } from "react";
import { Alert, Button, Input, Modal, Space, Typography, Upload, message } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { useManagedFiles } from "../../model/useManagedFiles";

export interface FileDraft { name: string; text: string; encoded?: string; revision?: string }
export function FileEditorDialog({ vm, editor, setEditor }: { vm: ReturnType<typeof useManagedFiles>; editor: FileDraft | null; setEditor: Dispatch<SetStateAction<FileDraft | null>> }) {
  const prefix = vm.partition?.key === "custom_templates" && vm.directory && vm.directory !== "." ? `${vm.directory}/` : "";
  return <>
    <Modal open={!!editor} title={editor?.revision ? "替换或编辑文件" : "上传或新建文件"} width={850} okText="保存" cancelText="取消" confirmLoading={vm.busy} onCancel={() => setEditor(null)} onOk={async () => {
      if (!editor) return;
      const encoded = editor.encoded ?? btoa(Array.from(new TextEncoder().encode(editor.text), byte => String.fromCharCode(byte)).join(""));
      if (await vm.mutate({ name: editor.name, operation: editor.revision ? "replace" : "create", revision: editor.revision, content_base64: encoded })) setEditor(null);
    }}>
      <Space direction="vertical" style={{ width: "100%" }}>
        <Alert showIcon type="info" message={editor?.revision ? "保存将替换原文件，请先下载备份；同名替换保持配置路径不变。" : "填写分区内相对路径；同名文件不会被覆盖，请先在列表中打开原文件再替换。"} />
        <Input aria-label="文件相对路径" prefix={prefix ? <Typography.Text type="secondary">{prefix}</Typography.Text> : undefined} placeholder={prefix ? "例如 report.typ 或 assets/character.png" : "例如 my_theme/report.typ；素材须使用主题清单中的文件名"} value={prefix && editor?.name.startsWith(prefix) ? editor.name.slice(prefix.length) : editor?.name} disabled={!!editor?.revision} onChange={event => setEditor(value => value && { ...value, name: prefix + event.target.value })} />
        {editor?.encoded !== undefined ? <Upload showUploadList={false} beforeUpload={async file => {
          if (file.size > 32 * 1024 * 1024) { void message.error("文件不得超过 32 MiB"); return false; }
          const reader = new FileReader(); reader.onload = () => setEditor(value => value && { ...value, encoded: String(reader.result).split(",")[1] }); reader.readAsDataURL(file); return false;
        }}><Button icon={<UploadOutlined />}>选择替换内容</Button></Upload> : <Input.TextArea aria-label="文件内容" value={editor?.text} rows={20} onChange={event => setEditor(value => value && { ...value, text: event.target.value })} />}
        <Typography.Text type="secondary">{vm.partition?.key === "custom_templates" ? "源码和素材按相对路径引用；请保留模板所需入口及引用关系。" : vm.partition?.key === "template_resources" ? "文件路径须与主题素材清单一致，可在素材状态页展开清单并复制路径。" : "同名替换会保留原配置引用路径。"}单文件最大 32 MiB，图片会校验格式与像素预算。</Typography.Text>
      </Space>
    </Modal>
  </>;
}
