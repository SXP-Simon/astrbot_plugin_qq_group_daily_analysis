import type { ManagedFileContent, ManagedPartition } from "../../entities/plugin-data/api/managedFilesApi";

const definitions: [string, string, string, boolean, boolean][] = [
  ["reports", "历史报告文件", "已生成的图片及 HTML 报告", false, true],
  ["custom_templates", "自定义报告模板", "已安装模板的源码及素材", true, true],
  ["config_files", "配置参考素材", "配置中心上传的角色参考图片", true, true],
  ["config_backups", "配置自动备份", "升级与迁移保留的配置，只读原件", false, true],
  ["typst_fonts", "Typst 字体", "主题共用字体，可按模板下载或上传", true, true],
  ["template_resources", "模板原始素材", "CDN 下载或手动替换的主题素材", true, true],
  ["typst_assets", "Typst 派生图片缓存", "裁切、缩放和透明度处理后的图片", false, true],
  ["typst_jobs", "Typst 渲染任务目录", "由渲染器管理的工作目录", false, false],
  ["preview_cache", "模板预览缓存", "模板画廊预览图片", false, true],
  ["hosted_reports", "托管 HTML 报告", "用于分享链接的 HTML 报告", false, true],
  ["legacy_history", "旧版历史记录", "旧版 JSON 记录；当前分析数据存储于 KV", false, true],
  ["avatar_storage", "头像缓存存储", "DiskCache 数据库与二进制，请通过头像条目管理", false, false],
  ["state", "状态与数据库", "链路、快照、去重数据库及状态文件", false, false],
];

const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect width="200" height="100" fill="#39c5bb"/><text x="15" y="55" fill="white">Miku report</text></svg>';
let revision = 0;
export const managedMockFiles = new Map<string, Map<string, ManagedFileContent>>();

export function putManagedMockFile(partition: string, name: string, text: string | null, encoded?: string) {
  let files = managedMockFiles.get(partition);
  if (!files) { files = new Map(); managedMockFiles.set(partition, files); }
  const content: ManagedFileContent = {
    name, text, content_base64: encoded ?? btoa(Array.from(new TextEncoder().encode(text || ""), byte => String.fromCharCode(byte)).join("")),
    revision: String(++revision).padStart(64, "0"),
    media_type: /\.(png|jpg|jpeg)$/.test(name) ? "image/" + (name.endsWith(".png") ? "png" : "jpeg") : name.endsWith(".svg") ? "image/svg+xml" : name.endsWith(".html") ? "text/html" : name.endsWith(".json") ? "application/json" : "text/plain",
  };
  files.set(name, content);
  return content;
}

putManagedMockFile("custom_templates", "my_miku/report.typ", '#set text(size: 12pt)\n= 群聊日报\n你好，初音未来！');
putManagedMockFile("custom_templates", "my_miku/template.json", '{"name":"我的初音模板"}');
putManagedMockFile("custom_templates", "my_miku/assets/character.svg", svg);
putManagedMockFile("custom_templates", "my_maria/report.typ", '#set text(size: 12pt)\n= Maria 群聊日报');
putManagedMockFile("custom_templates", "my_maria/template.json", '{"name":"我的 Maria 模板"}');
putManagedMockFile("custom_templates", "draft_theme/template.json", '{"name":"尚未完成的模板"}');
putManagedMockFile("reports", "123456789_2026-11-03.html", '<!doctype html><html><body style="font-family:sans-serif;color:#238b86"><h1>群聊日报</h1><p>今天共 384 条消息，12 位活跃成员。</p></body></html>');
putManagedMockFile("reports", "123456789_2026-11-03_miku.png", null, "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a27sAAAAASUVORK5CYII=");
putManagedMockFile("reports", "987654321_2026-11-02_maria.jpg", null, "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a27sAAAAASUVORK5CYII=");
putManagedMockFile("config_backups", "plugin_config_5.6.4_20261103.json", '{"plugin_version":"5.6.4","config":{"rendering":{"service":"typst"}}}');
putManagedMockFile("template_resources", "hack/globe.svg", svg);
putManagedMockFile("config_files", "character.svg", svg);
putManagedMockFile("typst_fonts", "NotoSansSC.ttf", null, "AAEAAAAA");
putManagedMockFile("typst_fonts", "NotoSansTC.ttf", null, "AAEAAAAA");
putManagedMockFile("preview_cache", "miku.svg", svg);
putManagedMockFile("state", "traces.db", null, "AA==");

export function managedMockPartitions(): ManagedPartition[] {
  return definitions.map(([key, name, description, writable, deletable]) => {
    const files = [...(managedMockFiles.get(key)?.values() || [])];
    return { key, name, description, writable, deletable, directory: `demo/plugin_data/${key}/`,
      impact: key === "custom_templates" ? "源码修改立即用于后续渲染，请先下载留存原版。" : key === "typst_fonts" ? "移除字体可能改变后续报告排版。" : key === "config_files" ? "重命名或删除会使配置中的旧路径失效。" : "操作影响此分区内文件，请先导出需要保留的内容。",
      count: files.length, size_bytes: files.reduce((sum, file) => sum + atob(file.content_base64).length, 0) };
  });
}

export const managedFileMockHandlers = {
  "GET plugin-data/partitions": () => ({ status: "ok", data: { items: managedMockPartitions() } }),
  "GET plugin-data/files": (query?: Record<string, unknown>) => {
    const partition = String(query?.partition);
    const extensions = String(query?.extensions || "").split(",").filter(Boolean);
    const all = [...(managedMockFiles.get(partition)?.values() || [])];
    const groups = new Map<string, { directory: string; count: number; size_bytes: number }>();
    if (partition === "custom_templates") for (const file of all) {
      const directory = file.name.includes("/") ? file.name.split("/")[0] : ".";
      const group = groups.get(directory) || { directory, count: 0, size_bytes: 0 };
      group.count++; group.size_bytes += atob(file.content_base64).length; groups.set(directory, group);
    }
    const directory = String(query?.directory || "");
    const items = all.filter(file => file.name.toLowerCase().includes(String(query?.search || "").toLowerCase()) && (!directory || (directory === "." ? !file.name.includes("/") : file.name.startsWith(directory + "/"))) && (!extensions.length || extensions.includes(file.name.split(".").pop()!.toLowerCase())));
    const start = (Number(query?.page || 1) - 1) * 20;
    return { status: "ok", data: { items: items.slice(start, start + 20).map(file => ({ name: file.name, revision: file.revision, media_type: file.media_type, size_bytes: atob(file.content_base64).length, modified_at: 1793692800, editable: partition === "custom_templates" && file.text !== null, downloadable: !["state", "avatar_storage"].includes(partition) })), total: items.length, groups: [...groups.values()].sort((a, b) => a.directory.localeCompare(b.directory)) } };
  },
  "GET plugin-data/files/content": (query?: Record<string, unknown>) => {
    const file = managedMockFiles.get(String(query?.partition))?.get(String(query?.name));
    return file ? { status: "ok", data: file } : { status: "error", message: "文件已不存在" };
  },
  "POST plugin-data/files/delete-many": (body?: Record<string, unknown>) => {
    const files = managedMockFiles.get(String(body?.partition));
    const deleted: string[] = [], failed: { name: string; message: string }[] = [];
    const selected = body?.files;
    if (!Array.isArray(selected)) return { status: "error", message: "请选择文件" };
    for (const item of selected) {
      const name = String(item.name);
      if (files?.get(name)?.revision !== item.revision) failed.push({ name, message: "文件已变更，请刷新后重选" });
      else { files?.delete(name); deleted.push(name); }
    }
    return { status: "ok", data: { deleted, failed } };
  },
  "POST plugin-data/files/mutate": (body?: Record<string, unknown>) => {
    const partition = String(body?.partition), name = String(body?.name), operation = body?.operation;
    const part = managedMockPartitions().find(item => item.key === partition);
    const files = managedMockFiles.get(partition), current = files?.get(name);
    if (!part || (operation === "delete" ? !part.deletable : !part.writable)) return { status: "error", message: "此分区不支持该操作" };
    if (operation === "create" ? !!current : !current || current.revision !== body?.revision) return { status: "error", message: "文件已变更或目标已存在，请刷新" };
    if (operation === "delete") files?.delete(name);
    else if (operation === "rename") {
      const newName = String(body?.new_name);
      if (files?.has(newName)) return { status: "error", message: "同名目标已存在" };
      putManagedMockFile(partition, newName, current?.text || null, current?.content_base64); files?.delete(name);
    } else {
      const encoded = String(body?.content_base64 || "");
      const text = /\.(typ|html|css|json|svg|txt|md)$/.test(name) ? new TextDecoder().decode(Uint8Array.from(atob(encoded), char => char.charCodeAt(0))) : null;
      putManagedMockFile(partition, name, text, encoded);
    }
    return { status: "ok", data: { success: true } };
  },
};
