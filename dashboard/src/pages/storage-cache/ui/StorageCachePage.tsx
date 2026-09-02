import React from "react";
import {
  Input,
  Select,
  Button,
  Popconfirm,
  Tooltip,
  Spin,
  Alert,
  Dropdown,
} from "antd";
import {
  ReloadOutlined,
  ThunderboltOutlined,
  DeleteOutlined,
  SearchOutlined,
  DatabaseOutlined,
  FolderOpenOutlined,
  FileZipOutlined,
  PictureOutlined,
  FileTextOutlined,
  CopyOutlined,
  LoadingOutlined,
  DownOutlined,
} from "@ant-design/icons";
import { useStorageCacheViewModel } from "../model/useStorageCacheViewModel";

export const StorageCachePage: React.FC = () => {
  const {
    storage,
    stats,
    resources,
    allResourcesCount,
    loading,
    prefetchProgress,
    clearing,
    selectedTemplate,
    setSelectedTemplate,
    selectedCategory,
    setSelectedCategory,
    searchQuery,
    setSearchQuery,
    availableTemplates,
    refresh,
    handlePrefetch,
    handleClear,
  } = useStorageCacheViewModel();

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const isSelectedSpecific = selectedTemplate && selectedTemplate !== "all";

  // 更多预取菜单选项
  const prefetchMenuItems = [
    {
      key: "all",
      label: "全量预取所有模板资源",
      icon: <ThunderboltOutlined className="text-amber-500" />,
      onClick: () => handlePrefetch("all"),
    },
    ...availableTemplates
      .filter((t) => t !== "global")
      .map((t) => ({
        key: t,
        label: `预取模板 [${t}]`,
        onClick: () => handlePrefetch(t),
      })),
  ];

  return (
    <div className="space-y-3">
      {/* 顶部紧凑状态与操作栏 (Header Toolbar) */}
      <div className="bg-white dark:bg-[#161b22] border border-[#e2e8f0] dark:border-[#30363d] rounded px-3 py-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <DatabaseOutlined className="text-blue-600 dark:text-blue-400 text-sm" />
          <span className="font-semibold text-xs md:text-sm text-[#1e293b] dark:text-[#c9d1d9]">
            存储空间全景与静态资源缓存控制台
          </span>
          <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono rounded bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800">
            ● 0 外网请求拦截就绪
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            size="small"
            icon={<ReloadOutlined spin={loading} />}
            onClick={() => refresh(true)}
            className="text-xs rounded border border-[#e2e8f0] dark:border-[#30363d] bg-white dark:bg-[#21262d] text-[#1e293b] dark:text-[#c9d1d9]"
          >
            刷新
          </Button>

          {/* 细粒度预取按钮组 */}
          {isSelectedSpecific ? (
            <Button
              type="primary"
              size="small"
              icon={
                prefetchProgress.active ? (
                  <LoadingOutlined />
                ) : (
                  <ThunderboltOutlined />
                )
              }
              loading={prefetchProgress.active}
              onClick={() => handlePrefetch(selectedTemplate)}
              className="text-xs rounded bg-[#2563eb] text-white hover:bg-blue-700 font-medium"
            >
              预取当前模板 [{selectedTemplate}]
            </Button>
          ) : (
            <Button
              type="primary"
              size="small"
              icon={
                prefetchProgress.active ? (
                  <LoadingOutlined />
                ) : (
                  <ThunderboltOutlined />
                )
              }
              loading={prefetchProgress.active}
              onClick={() => handlePrefetch("all")}
              className="text-xs rounded bg-[#2563eb] text-white hover:bg-blue-700 font-medium"
            >
              全量预取所有模板
            </Button>
          )}

          <Dropdown
            menu={{ items: prefetchMenuItems }}
            placement="bottomRight"
            disabled={prefetchProgress.active}
          >
            <Button
              size="small"
              icon={<DownOutlined className="text-[10px]" />}
              className="text-xs rounded px-1.5"
            />
          </Dropdown>

          <Popconfirm
            title="确认清理静态资源缓存？"
            description={
              isSelectedSpecific
                ? `将清理模板 [${selectedTemplate}] 下的所有已缓存资源文件`
                : "将清空全部已缓存的字体、样式表和图片资源"
            }
            onConfirm={() => handleClear()}
            okText="确认清理"
            cancelText="取消"
            okButtonProps={{ danger: true, size: "small" }}
            cancelButtonProps={{ size: "small" }}
          >
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              loading={clearing}
              className="text-xs rounded font-medium"
            >
              {isSelectedSpecific
                ? `清理模板 [${selectedTemplate}] 缓存`
                : "清理全部缓存"}
            </Button>
          </Popconfirm>
        </div>
      </div>

      {/* 友好预取中进度与耗时提示卡片 (Friendly Prefetch Alert) */}
      {prefetchProgress.active && (
        <Alert
          type="info"
          showIcon
          icon={<LoadingOutlined className="text-blue-500 text-sm" />}
          message={
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-medium">
              <span>
                正在预取【{prefetchProgress.templateName}】的外部字体与样式表...
              </span>
              <span className="font-mono text-blue-600 dark:text-blue-400">
                已耗时：{prefetchProgress.elapsedSeconds} 秒
              </span>
            </div>
          }
          description={
            <div className="text-[11px] text-[#64748b] dark:text-[#8b949e] mt-0.5">
              系统正在后台下载 Google Fonts / CDN
              字体切片并持久化写入本地缓存，国内网络初次拉取切片较多，请耐心等待...
            </div>
          }
          className="border border-blue-200 dark:border-blue-900 bg-blue-50/70 dark:bg-blue-950/30 rounded py-2 px-3"
        />
      )}

      {/* 1. Plugin Data 存储空间概览 (KPI Cards) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {/* 总占用 */}
        <div className="bg-white dark:bg-[#161b22] border border-[#e2e8f0] dark:border-[#30363d] rounded px-3 py-2 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-[#64748b] dark:text-[#8b949e]">
            <span className="font-medium">数据目录总空间</span>
            <FolderOpenOutlined />
          </div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="font-mono font-semibold text-base md:text-lg text-[#1e293b] dark:text-[#c9d1d9]">
              {storage?.total?.mb ?? 0}
            </span>
            <span className="text-[10px] text-[#64748b] dark:text-[#8b949e]">
              MB ({storage?.total?.files ?? 0} 项)
            </span>
          </div>
        </div>

        {/* 静态资源缓存 */}
        <div className="bg-white dark:bg-[#161b22] border border-[#e2e8f0] dark:border-[#30363d] rounded px-3 py-2 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-[#64748b] dark:text-[#8b949e]">
            <span className="font-medium">静态资源与字体缓存</span>
            <FileZipOutlined className="text-amber-500" />
          </div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="font-mono font-semibold text-base md:text-lg text-amber-600 dark:text-amber-400">
              {storage?.resources_cache?.mb ?? 0}
            </span>
            <span className="text-[10px] text-[#64748b] dark:text-[#8b949e]">
              MB ({storage?.resources_cache?.files ?? 0} 文件)
            </span>
          </div>
        </div>

        {/* SQLite 链路库 */}
        <div className="bg-white dark:bg-[#161b22] border border-[#e2e8f0] dark:border-[#30363d] rounded px-3 py-2 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-[#64748b] dark:text-[#8b949e]">
            <span className="font-medium">链路数据库 (Traces)</span>
            <DatabaseOutlined className="text-blue-500" />
          </div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="font-mono font-semibold text-base md:text-lg text-blue-600 dark:text-blue-400">
              {storage?.database?.traces_sqlite_mb ?? 0}
            </span>
            <span className="text-[10px] text-[#64748b] dark:text-[#8b949e]">
              MB (SQLite)
            </span>
          </div>
        </div>

        {/* 产物报告 */}
        <div className="bg-white dark:bg-[#161b22] border border-[#e2e8f0] dark:border-[#30363d] rounded px-3 py-2 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-[#64748b] dark:text-[#8b949e]">
            <span className="font-medium">历史报告与图片</span>
            <PictureOutlined className="text-purple-500" />
          </div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="font-mono font-semibold text-base md:text-lg text-[#1e293b] dark:text-[#c9d1d9]">
              {storage?.reports?.mb ?? 0}
            </span>
            <span className="text-[10px] text-[#64748b] dark:text-[#8b949e]">
              MB ({storage?.reports?.files ?? 0} 份)
            </span>
          </div>
        </div>

        {/* 增量与断点 */}
        <div className="bg-white dark:bg-[#161b22] border border-[#e2e8f0] dark:border-[#30363d] rounded px-3 py-2 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-[#64748b] dark:text-[#8b949e]">
            <span className="font-medium">断点与增量记录</span>
            <FileTextOutlined className="text-emerald-500" />
          </div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="font-mono font-semibold text-base md:text-lg text-[#1e293b] dark:text-[#c9d1d9]">
              {storage?.checkpoints?.mb ?? 0}
            </span>
            <span className="text-[10px] text-[#64748b] dark:text-[#8b949e]">
              MB ({storage?.checkpoints?.files ?? 0} 项)
            </span>
          </div>
        </div>

        {/* 头像缓存 */}
        <div className="bg-white dark:bg-[#161b22] border border-[#e2e8f0] dark:border-[#30363d] rounded px-3 py-2 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-[#64748b] dark:text-[#8b949e]">
            <span className="font-medium">用户头像缓存</span>
            <PictureOutlined className="text-cyan-500" />
          </div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="font-mono font-semibold text-base md:text-lg text-[#1e293b] dark:text-[#c9d1d9]">
              {storage?.avatars?.mb ?? 0}
            </span>
            <span className="text-[10px] text-[#64748b] dark:text-[#8b949e]">
              MB ({storage?.avatars?.files ?? 0} 张)
            </span>
          </div>
        </div>
      </div>

      {/* 2. 静态资源与字体缓存看板 (按模板组织) */}
      <div className="bg-white dark:bg-[#161b22] border border-[#e2e8f0] dark:border-[#30363d] rounded overflow-hidden">
        {/* 表头筛选与搜索栏 */}
        <div className="p-2.5 border-b border-[#e2e8f0] dark:border-[#30363d] flex flex-wrap items-center justify-between gap-2 bg-[#f8fafc] dark:bg-[#161b22]/80">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-[#1e293b] dark:text-[#c9d1d9]">
              模板资源缓存
            </span>

            {/* 模板选择 */}
            <Select
              size="small"
              value={selectedTemplate}
              onChange={setSelectedTemplate}
              style={{ width: 140 }}
              className="text-xs font-mono"
              options={[
                { label: "全部模板", value: "all" },
                { label: "global (通用)", value: "global" },
                ...availableTemplates
                  .filter((t) => t !== "global")
                  .map((t) => ({ label: t, value: t })),
              ]}
            />

            {/* 分类选择 */}
            <Select
              size="small"
              value={selectedCategory}
              onChange={setSelectedCategory}
              style={{ width: 120 }}
              className="text-xs font-mono"
              options={[
                { label: "全部分类", value: "all" },
                {
                  label: `字体 (${stats?.by_category?.fonts?.files ?? 0})`,
                  value: "fonts",
                },
                {
                  label: `CSS (${stats?.by_category?.css?.files ?? 0})`,
                  value: "css",
                },
                {
                  label: `图片 (${stats?.by_category?.images?.files ?? 0})`,
                  value: "images",
                },
                {
                  label: `脚本 (${stats?.by_category?.scripts?.files ?? 0})`,
                  value: "scripts",
                },
              ]}
            />

            {/* 搜索框 */}
            <Input
              size="small"
              placeholder="搜索 URL / 路径 / MIME..."
              prefix={<SearchOutlined className="text-slate-400" />}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              allowClear
              style={{ width: 220 }}
              className="text-xs"
            />
          </div>

          <div className="flex items-center gap-2 text-[10px] text-[#64748b] dark:text-[#8b949e]">
            <span>
              已加载{" "}
              <strong className="font-mono text-[#1e293b] dark:text-[#c9d1d9]">
                {resources.length}
              </strong>{" "}
              / {allResourcesCount} 项
            </span>
            <span>•</span>
            <span>
              总命中访问{" "}
              <strong className="font-mono text-emerald-600 dark:text-emerald-400">
                {stats?.total_access_count ?? 0}
              </strong>{" "}
              次
            </span>
          </div>
        </div>

        {/* 紧凑数据表格 (Data-Dense Table) */}
        {loading ? (
          <div className="p-8 text-center">
            <Spin tip="正在读取静态资源索引..." />
          </div>
        ) : resources.length === 0 ? (
          <div className="p-8 text-center text-xs text-[#64748b] dark:text-[#8b949e]">
            暂无已缓存资源。在日常分析实际渲染时将自动按需缓存；亦可点击上方按钮手动预取。
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[#e2e8f0] dark:border-[#30363d] bg-[#f8fafc] dark:bg-[#161b22]/60 text-[10px] md:text-xs uppercase tracking-wider text-[#64748b] dark:text-[#8b949e]">
                  <th className="py-2 px-3 font-medium">模板归属</th>
                  <th className="py-2 px-3 font-medium">分类</th>
                  <th className="py-2 px-3 font-medium">资源 URL</th>
                  <th className="py-2 px-3 font-medium">MIME 类型</th>
                  <th className="py-2 px-3 font-medium">本地大小</th>
                  <th className="py-2 px-3 font-medium">命中次数</th>
                  <th className="py-2 px-3 font-medium">相对路径</th>
                  <th className="py-2 px-3 font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e2e8f0] dark:divide-[#30363d]">
                {resources.map((item) => (
                  <tr
                    key={item.hash}
                    className="hover:bg-[#f8fafc] dark:hover:bg-[#21262d] transition-colors"
                  >
                    <td className="py-1.5 px-3">
                      <span className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                        {item.template || "global"}
                      </span>
                    </td>
                    <td className="py-1.5 px-3">
                      <span
                        className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono rounded border ${
                          item.category === "fonts"
                            ? "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800"
                            : item.category === "css"
                            ? "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-800"
                            : item.category === "scripts"
                            ? "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-400 dark:border-purple-800"
                            : "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800"
                        }`}
                      >
                        {item.category}
                      </span>
                    </td>
                    <td className="py-1.5 px-3 font-mono text-[#1e293b] dark:text-[#c9d1d9] max-w-[280px] truncate">
                      <Tooltip title={item.url}>
                        <span className="cursor-pointer select-all">
                          {item.url}
                        </span>
                      </Tooltip>
                    </td>
                    <td className="py-1.5 px-3 font-mono text-[#64748b] dark:text-[#8b949e] text-[11px]">
                      {item.mime_type}
                    </td>
                    <td className="py-1.5 px-3 font-mono text-[#64748b] dark:text-[#8b949e]">
                      {item.size_formatted ||
                        `${(item.size / 1024).toFixed(1)} KB`}
                    </td>
                    <td className="py-1.5 px-3 font-mono font-medium text-emerald-600 dark:text-emerald-400">
                      {item.access_count ?? 1}
                    </td>
                    <td className="py-1.5 px-3 font-mono text-[10px] text-[#64748b] dark:text-[#8b949e] max-w-[200px] truncate">
                      <Tooltip title={item.relative_path || item.file_path}>
                        <span>{item.relative_path || item.file_path}</span>
                      </Tooltip>
                    </td>
                    <td className="py-1.5 px-3 text-right">
                      <Button
                        type="text"
                        size="small"
                        icon={<CopyOutlined className="text-[10px]" />}
                        onClick={() => handleCopy(item.url)}
                        className="text-[11px] px-1 text-[#2563eb] dark:text-[#58a6ff]"
                      >
                        复制链接
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
