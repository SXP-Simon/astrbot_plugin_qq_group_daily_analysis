import { useEffect, useMemo, useState } from "react";
import { message } from "antd";
import { fetchReportHistory, fetchReportContent } from "../../../entities/report/api/reportApi";
import { fetchDistinctGroups } from "../../../entities/group/api/groupApi";
import { ReportItem } from "../../../entities/report/model/types";
import { GroupItem } from "../../../entities/group/model/types";

export function useReportsViewModel() {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [loading, setLoading] = useState(false);

  // 过滤筛选状态
  const [search, setSearch] = useState("");
  const [selectedGroup, setSelectedGroup] = useState<string | undefined>(undefined);
  const [dateRange, setDateRange] = useState<[number, number] | null>(null);

  // 预览状态
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [selectedReport, setSelectedReport] = useState<ReportItem | null>(null);

  const loadReports = async () => {
    setLoading(true);
    try {
      const [reportList, groupList] = await Promise.all([
        fetchReportHistory(),
        fetchDistinctGroups().catch(() => []),
      ]);
      setReports(reportList);
      setGroups(groupList);
    } catch {
      // 忽略加载异常
    } finally {
      setLoading(false);
    }
  };

  const openPreview = async (report: ReportItem) => {
    setSelectedReport(report);
    setPreviewOpen(true);
    setPreviewLoading(true);
    try {
      const data = await fetchReportContent(report.filename);
      if (data && (data.data_url || data.html_content)) {
        setSelectedReport((prev) => ({
          ...(prev || report),
          ...data,
        }));
      } else {
        message.warning("未能读取到报告文件数据");
      }
    } catch {
      message.error("加载报告文件失败");
    } finally {
      setPreviewLoading(false);
    }
  };

  const closePreview = () => {
    setPreviewOpen(false);
    setSelectedReport(null);
  };

  const downloadReport = async (report: ReportItem) => {
    try {
      const isHtml = Boolean(
        report.is_html ||
          report.filename.toLowerCase().endsWith(".html") ||
          report.filename.toLowerCase().endsWith(".htm")
      );
      let href = report.data_url;
      let cleanupBlobUrl: string | null = null;

      if (isHtml && report.html_content) {
        const blob = new Blob([report.html_content], { type: "text/html;charset=utf-8" });
        cleanupBlobUrl = URL.createObjectURL(blob);
        href = cleanupBlobUrl;
      } else if (!href) {
        const data = await fetchReportContent(report.filename);
        if (data) {
          if (isHtml && data.html_content) {
            const blob = new Blob([data.html_content], { type: "text/html;charset=utf-8" });
            cleanupBlobUrl = URL.createObjectURL(blob);
            href = cleanupBlobUrl;
          } else {
            href = data.data_url;
          }
        }
      }

      if (!href) {
        message.error("获取下载文件失败");
        return;
      }

      const a = document.createElement("a");
      a.href = href;
      a.download = report.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      if (cleanupBlobUrl) {
        URL.revokeObjectURL(cleanupBlobUrl);
      }
      message.success(`已开始下载 ${report.filename}`);
    } catch {
      message.error("下载文件异常");
    }
  };

  // 综合计算筛选后的报告列表
  const filteredReports = useMemo(() => {
    return reports.filter((item) => {
      // 1. 群聊筛选
      if (selectedGroup) {
        if (item.group_id !== selectedGroup && !item.filename.includes(selectedGroup)) {
          return false;
        }
      }

      // 2. 日期范围筛选 (基于 modified_at 时间戳)
      if (dateRange && dateRange[0] && dateRange[1]) {
        if (item.modified_at < dateRange[0] || item.modified_at > dateRange[1]) {
          return false;
        }
      }

      // 3. 关键字搜索（支持文件名、群号、群名、绝对路径、TraceID）
      if (search.trim()) {
        const kw = search.trim().toLowerCase();
        const matchName = item.filename.toLowerCase().includes(kw);
        const matchGid = (item.group_id || "").toLowerCase().includes(kw);
        const matchGname = (item.group_name || "").toLowerCase().includes(kw);
        const matchPath = (item.absolute_path || "").toLowerCase().includes(kw);
        const matchTrace = (item.trace_id || "").toLowerCase().includes(kw);
        if (!matchName && !matchGid && !matchGname && !matchPath && !matchTrace) {
          return false;
        }
      }

      return true;
    });
  }, [reports, selectedGroup, dateRange, search]);

  // 合并来自报告元数据的群聊选项，保证未入库群聊也能正常筛选
  const mergedGroups = useMemo(() => {
    const map = new Map<string, GroupItem>();
    for (const g of groups) {
      map.set(g.group_id, g);
    }
    for (const r of reports) {
      if (r.group_id && !map.has(r.group_id)) {
        map.set(r.group_id, {
          group_id: r.group_id,
          group_name: r.group_name || `群 ${r.group_id}`,
          platform: "qq",
        });
      }
    }
    return Array.from(map.values());
  }, [groups, reports]);

  useEffect(() => {
    loadReports();
  }, []);

  return {
    reports: filteredReports,
    rawReports: reports,
    groups: mergedGroups,
    loading,
    search,
    setSearch,
    selectedGroup,
    setSelectedGroup,
    dateRange,
    setDateRange,
    refresh: loadReports,
    previewOpen,
    previewLoading,
    selectedReport,
    openPreview,
    closePreview,
    downloadReport,
  };
}


