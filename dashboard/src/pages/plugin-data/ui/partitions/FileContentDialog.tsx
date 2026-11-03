import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import { Alert, Button, Image, Input, Modal, Popconfirm, Space, Tabs, Typography } from "antd";
import { DownloadOutlined, EditOutlined } from "@ant-design/icons";
import { useManagedFiles } from "../../model/useManagedFiles";
import { FileEditorDialog, type FileDraft } from "./FileEditorDialog";

export function FileContentDialog({ vm, editor, setEditor, references }: { vm: ReturnType<typeof useManagedFiles>; editor: FileDraft | null; setEditor: Dispatch<SetStateAction<FileDraft | null>>; references?: string[] }) {
  const [rename, setRename] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const currentFile = vm.files.find(file => file.name === vm.content?.name);
  const prefix = vm.partition?.key === "custom_templates" && vm.directory && vm.directory !== "." ? `${vm.directory}/` : "";
  useEffect(() => {
    if (!vm.content) { setPreviewUrl(""); return; }
    const bytes = Uint8Array.from(atob(vm.content.content_base64), char => char.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: vm.content.media_type }));
    setPreviewUrl(url);
    return () => { URL.revokeObjectURL(url); };
  }, [vm.content]);

  const download = () => {
    if (!vm.content) return;
    const link = document.createElement("a");
    link.href = previewUrl; link.download = vm.content.name.split("/").pop() || "download"; link.click();
  };
  return <>
    <Modal open={!!vm.content} title={vm.content?.name} width={900} onCancel={() => vm.setContent(null)} footer={<Space wrap>
      <Button icon={<DownloadOutlined />} onClick={download}>下载原文件</Button>
      {currentFile?.editable && <Button icon={<EditOutlined />} onClick={() => setEditor({ name: vm.content!.name, text: vm.content!.text || "", revision: vm.content!.revision })}>编辑源码</Button>}
      {vm.partition?.writable && <Button onClick={() => setEditor({ name: vm.content!.name, text: vm.content!.text || "", revision: vm.content!.revision, encoded: vm.content!.content_base64 })}>替换文件</Button>}
      {["custom_templates", "config_files"].includes(vm.partition?.key || "") && <Button onClick={() => setRename(vm.content!.name)}>重命名</Button>}
      {vm.partition?.deletable && <Popconfirm title="删除此文件？" description={vm.partition.impact} onConfirm={() => vm.mutate({ operation: "delete", name: vm.content!.name, revision: vm.content!.revision })}><Button danger loading={vm.busy}>删除文件</Button></Popconfirm>}
      <Button onClick={() => vm.setContent(null)}>关闭</Button>
    </Space>}>
      {vm.content && <Space direction="vertical" style={{ width: "100%" }}>
        {!!references?.length && <Alert type="warning" showIcon message="此图片正在被配置引用；同名替换保留引用，重命名或删除会使旧路径失效。" description={<Typography.Text style={{ overflowWrap: "anywhere" }}>{references.join("、")}</Typography.Text>} />}
        {vm.content.media_type.startsWith("image/") ? <Image src={previewUrl} style={{ maxHeight: 480, objectFit: "contain" }} /> : vm.content.media_type === "text/html" ? <Tabs items={[{ key: "preview", label: "隔离预览", children: <iframe title="报告预览" sandbox="" srcDoc={vm.content.text || ""} style={{ width: "100%", height: 480, border: "1px solid #ddd" }} /> }, { key: "source", label: "HTML 源码", children: <Input.TextArea readOnly value={vm.content.text || ""} rows={18} /> }]} /> : vm.content.text !== null ? <Input.TextArea readOnly value={vm.content.text} rows={18} /> : <Alert type="info" message="此二进制文件可下载后使用对应应用查看" />}
      </Space>}
      {vm.content && <FileEditorDialog vm={vm} editor={editor} setEditor={setEditor} />}
    <Modal open={!!vm.content && rename !== null} title="重命名文件" okText="重命名" cancelText="取消" confirmLoading={vm.busy} onCancel={() => setRename(null)} onOk={async () => {
      if (vm.content && rename && await vm.mutate({ operation: "rename", name: vm.content.name, revision: vm.content.revision, new_name: rename })) setRename(null);
    }}><Alert type="warning" message="重命名后，模板或配置中引用的旧路径需要同步更新。" style={{ marginBottom: 12 }} /><Input aria-label="新文件名" prefix={prefix ? <Typography.Text type="secondary">{prefix}</Typography.Text> : undefined} value={prefix && rename?.startsWith(prefix) ? rename.slice(prefix.length) : rename || ""} onChange={event => setRename(prefix + event.target.value)} /></Modal>
    </Modal>
  </>;
}
