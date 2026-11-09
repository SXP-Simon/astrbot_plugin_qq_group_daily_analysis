const imageFilters = [
  { value: "jpg,jpeg,png", label: "JPG + PNG" },
  { value: "jpg,jpeg", label: "JPG" },
  { value: "png", label: "PNG" },
  { value: "svg", label: "SVG" },
  { value: "webp,gif", label: "WebP / GIF" },
];
const jsonFilters = [{ value: "json", label: "JSON" }];

export type PartitionNavigation =
  | { kind: "page"; destination: "reports" | "config" | "traces"; label: string }
  | { kind: "data"; destination: "records" | "incremental" | "checkpoints"; label: string };

const currentRecords: PartitionNavigation = {
  kind: "data",
  destination: "records",
  label: "管理当前分析存档",
};
const executionTasks: PartitionNavigation = {
  kind: "page",
  destination: "traces",
  label: "查看分析执行任务",
};
const reportHistory: PartitionNavigation = {
  kind: "page",
  destination: "reports",
  label: "打开历史报告预览与重绘",
};
export const partitionNavigation: Record<string, PartitionNavigation[]> = {
  reports: [reportHistory],
  hosted_reports: [reportHistory],
  config_files: [{ kind: "page", destination: "config", label: "在配置中心新增图片与维护引用" }],
  config_backups: [{ kind: "page", destination: "config", label: "打开配置中心" }],
  state: [
    executionTasks,
    currentRecords,
    { kind: "data", destination: "incremental", label: "管理增量批次" },
    { kind: "data", destination: "checkpoints", label: "管理阶段快照" },
  ],
  typst_jobs: [executionTasks],
  legacy_history: [currentRecords],
};

export const partitionPresentation: Record<
  string,
  {
    capabilities: string[];
    filters: { value: string; label: string }[];
    empty: string;
  }
> = {
  reports: {
    capabilities: ["报告预览", "下载 / 多选删除"],
    filters: [{ value: "html,htm", label: "HTML" }, ...imageFilters],
    empty: "尚未生成报告；完成分析后，保存的报告会显示在这里。",
  },
  custom_templates: {
    capabilities: ["安装 / 卸载", "源码编辑", "素材维护"],
    filters: [
      { value: "typ", label: "Typst 模板（.typ）" },
      { value: "html,htm", label: "HTML" },
      ...jsonFilters,
      { value: "css,js,txt,md,yaml,yml", label: "其他源码" },
      { value: "jpg,jpeg,png,svg,webp,gif", label: "图片素材" },
      { value: "ttf,otf,ttc", label: "模板字体" },
    ],
    empty: "尚未安装自定义模板；可以安装模板包，或新建模板源码。内置模板不在此分区。",
  },
  config_files: {
    capabilities: ["图片预览", "上传 / 替换", "配置引用"],
    filters: imageFilters,
    empty: "尚未上传配置参考图片；可在此上传，或在配置中心设置参考图。",
  },
  config_backups: {
    capabilities: ["版本与内容查阅", "下载 / 多选删除"],
    filters: jsonFilters,
    empty: "暂无自动备份；插件升级或配置迁移时会按需创建。",
  },
  typst_fonts: {
    capabilities: ["模板依赖", "补齐 / 替换 / 移除"],
    filters: [],
    empty: "尚未安装字体，请按报告模板补齐所需字体。",
  },
  template_resources: {
    capabilities: ["主题素材状态", "CDN 补齐", "本地替换"],
    filters: imageFilters,
    empty: "本地暂无素材；可在“主题素材状态”中按模板从 CDN 补齐。",
  },
  typst_assets: {
    capabilities: ["图片预览", "多选清理", "按需重建"],
    filters: imageFilters,
    empty: "暂无派生图片；Typst 渲染时会按需生成，无需手动上传。",
  },
  typst_jobs: {
    capabilities: ["渲染诊断", "只读下载"],
    filters: [
      { value: "typ", label: "Typst（.typ）" },
      ...jsonFilters,
      { value: "txt,log", label: "诊断文本" },
      ...imageFilters,
    ],
    empty: "暂无保留的渲染工作文件；工作目录由渲染器创建和回收。",
  },
  preview_cache: {
    capabilities: ["预览图查看", "多选清理", "按需重建"],
    filters: imageFilters,
    empty: "暂无模板预览缓存；打开模板画廊生成预览后会自动建立。",
  },
  comic_preview_cache: {
    capabilities: ["样图预览 / 下载", "重新获取", "多选清理"],
    filters: [],
    empty: "暂无漫画样图缓存。可选择风格获取样图，群聊预览也会按需建立缓存。",
  },
  hosted_reports: {
    capabilities: ["HTML 预览", "下载 / 多选删除", "分享链接维护"],
    filters: [{ value: "html,htm", label: "HTML" }],
    empty: "暂无托管报告；启用报告链接分享并生成报告后会显示在这里。",
  },
  legacy_history: {
    capabilities: ["旧 JSON 查阅", "下载 / 多选删除", "当前存档入口"],
    filters: jsonFilters,
    empty: "没有旧版 JSON 历史文件；当前分析存档请前往“分析存档与头像”。",
  },
  avatar_storage: {
    capabilities: ["头像预览与下载", "按条目清理"],
    filters: [],
    empty: "暂无头像缓存。",
  },
  state: {
    capabilities: ["数据库占用", "任务 / 批次 / 快照入口"],
    filters: [{ value: "db,sqlite,sqlite3,db-wal,db-shm", label: "数据库" }, ...jsonFilters],
    empty: "暂无状态文件；分析任务运行后会按需创建。",
  },
};
