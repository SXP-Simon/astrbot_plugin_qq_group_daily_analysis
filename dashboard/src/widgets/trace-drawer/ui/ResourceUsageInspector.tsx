import React, { useState } from "react";
import { Typography, Tooltip, Button } from "antd";
import {
  CheckCircleOutlined,
  CloudDownloadOutlined,
  FileZipOutlined,
  DownOutlined,
  UpOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { ResourceLocalizationTelemetry } from "../../../entities/resource/model/types";

const { Text } = Typography;

interface ResourceUsageInspectorProps {
  data?: ResourceLocalizationTelemetry | null;
}

export const ResourceUsageInspector: React.FC<ResourceUsageInspectorProps> = ({
  data,
}) => {
  const [expanded, setExpanded] = useState(false);

  if (!data || data.total_intercepted === 0) {
    return null;
  }

  const inlinedKb = (data.inlined_bytes / 1024).toFixed(1);
  const isAllCached =
    data.cache_hits + data.local_asset_hits === data.total_intercepted;

  return (
    <div className="bg-white dark:bg-[#161b22] border border-[#e2e8f0] dark:border-[#30363d] rounded p-2.5 my-2">
      {/* 顶部标题与零网络保证状态 */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2 pb-1.5 border-b border-[#e2e8f0] dark:border-[#30363d]">
        <div className="flex items-center gap-1.5">
          <ThunderboltOutlined className="text-amber-500 text-xs" />
          <span className="text-xs font-semibold text-[#1e293b] dark:text-[#c9d1d9]">
            静态资源与字体本地化（0 外网请求保证）
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
            {data.template || "default"}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono font-medium rounded border ${
              isAllCached
                ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800"
                : "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-800"
            }`}
          >
            <CheckCircleOutlined className="mr-1 text-[10px]" />
            {isAllCached ? "100% 缓存命中" : `命中率 ${data.hit_rate}%`}
          </span>
          <span className="text-[10px] font-mono text-[#64748b] dark:text-[#8b949e]">
            耗时 {data.duration_ms}ms
          </span>
        </div>
      </div>

      {/* 紧凑指标网格 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 mb-2 text-xs">
        <div className="bg-[#f8fafc] dark:bg-[#21262d] border border-[#e2e8f0] dark:border-[#30363d] rounded px-2 py-1">
          <div className="text-[10px] text-[#64748b] dark:text-[#8b949e]">
            拦截资源总数
          </div>
          <div className="font-mono font-semibold text-[#1e293b] dark:text-[#c9d1d9] mt-0.5">
            {data.total_intercepted} 个
          </div>
        </div>

        <div className="bg-[#f8fafc] dark:bg-[#21262d] border border-[#e2e8f0] dark:border-[#30363d] rounded px-2 py-1">
          <div className="text-[10px] text-[#64748b] dark:text-[#8b949e]">
            缓存/本地命中
          </div>
          <div className="font-mono font-semibold text-emerald-600 dark:text-emerald-400 mt-0.5">
            {data.cache_hits + data.local_asset_hits}
            <span className="text-[10px] font-normal text-[#64748b] dark:text-[#8b949e] ml-1">
              (本地: {data.local_asset_hits})
            </span>
          </div>
        </div>

        <div className="bg-[#f8fafc] dark:bg-[#21262d] border border-[#e2e8f0] dark:border-[#30363d] rounded px-2 py-1">
          <div className="text-[10px] text-[#64748b] dark:text-[#8b949e]">
            网络新下载
          </div>
          <div className="font-mono font-semibold text-blue-600 dark:text-blue-400 mt-0.5">
            {data.downloaded}
          </div>
        </div>

        <div className="bg-[#f8fafc] dark:bg-[#21262d] border border-[#e2e8f0] dark:border-[#30363d] rounded px-2 py-1">
          <div className="text-[10px] text-[#64748b] dark:text-[#8b949e]">
            内联数据体积
          </div>
          <div className="font-mono font-semibold text-[#1e293b] dark:text-[#c9d1d9] mt-0.5">
            {inlinedKb} KB
          </div>
        </div>
      </div>

      {/* 折叠展开资源列表明细 */}
      <div className="flex items-center justify-between pt-1">
        <span className="text-[10px] text-[#64748b] dark:text-[#8b949e]">
          已拦截转换为 Base64 Data URI，Playwright 渲染 0 外网请求
        </span>
        <Button
          type="link"
          size="small"
          className="p-0 text-xs font-mono text-[#2563eb] dark:text-[#58a6ff]"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <>
              收起明细 <UpOutlined className="text-[10px] ml-1" />
            </>
          ) : (
            <>
              查看资源明细 ({data.items?.length || 0}){" "}
              <DownOutlined className="text-[10px] ml-1" />
            </>
          )}
        </Button>
      </div>

      {expanded && data.items && data.items.length > 0 && (
        <div className="mt-2 pt-2 border-t border-[#e2e8f0] dark:border-[#30363d] overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-[#e2e8f0] dark:border-[#30363d] bg-[#f8fafc] dark:bg-[#21262d]/60 text-[10px] uppercase tracking-wider text-[#64748b] dark:text-[#8b949e]">
                <th className="py-1 px-2 font-medium">类型</th>
                <th className="py-1 px-2 font-medium">资源 URL</th>
                <th className="py-1 px-2 font-medium">MIME 类型</th>
                <th className="py-1 px-2 font-medium">大小</th>
                <th className="py-1 px-2 font-medium">来源</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e2e8f0] dark:divide-[#30363d]">
              {data.items.map((item, idx) => (
                <tr
                  key={idx}
                  className="hover:bg-[#f8fafc] dark:hover:bg-[#21262d] transition-colors"
                >
                  <td className="py-1 px-2">
                    <span className="px-1 py-0.2 text-[10px] font-mono rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                      {item.type}
                    </span>
                  </td>
                  <td className="py-1 px-2 font-mono text-[11px] text-[#1e293b] dark:text-[#c9d1d9] max-w-[240px] truncate">
                    <Tooltip title={item.url}>
                      <span>{item.url}</span>
                    </Tooltip>
                  </td>
                  <td className="py-1 px-2 font-mono text-[11px] text-[#64748b] dark:text-[#8b949e]">
                    {item.mime}
                  </td>
                  <td className="py-1 px-2 font-mono text-[11px] text-[#64748b] dark:text-[#8b949e]">
                    {(item.size / 1024).toFixed(1)} KB
                  </td>
                  <td className="py-1 px-2">
                    {item.cached ? (
                      <span className="text-emerald-600 dark:text-emerald-400 font-mono text-[10px] inline-flex items-center gap-1">
                        <FileZipOutlined /> 本地缓存
                      </span>
                    ) : (
                      <span className="text-blue-600 dark:text-blue-400 font-mono text-[10px] inline-flex items-center gap-1">
                        <CloudDownloadOutlined /> 网络下载
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
