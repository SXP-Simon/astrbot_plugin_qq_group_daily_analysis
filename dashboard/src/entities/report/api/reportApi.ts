import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";
import { ReportItem } from "../model/types";
import { ReportTemplateItem, DEFAULT_REPORT_TEMPLATES } from "../model/templates";

export async function fetchReportHistory(): Promise<ReportItem[]> {
  const res = await apiGet<ReportItem[]>("reports/history");
  const data = extractData<ReportItem[]>(res);
  if (Array.isArray(data)) return data;
  return [];
}

export async function fetchReportContent(filename: string): Promise<ReportItem | null> {
  const res = await apiGet<ReportItem>("reports/content", { filename });
  const data = extractData<ReportItem>(res);
  return data || null;
}

export async function fetchReportTemplates(): Promise<ReportTemplateItem[]> {
  try {
    const res = await apiGet<ReportTemplateItem[]>("reports/templates");
    const data = extractData<ReportTemplateItem[]>(res);
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // fallback to defaults on network/bridge error
  }
  return DEFAULT_REPORT_TEMPLATES;
}

export async function rerenderReport(params: {
  group_id: string;
  date_str?: string;
  template_name?: string;
  render_format?: "image" | "html";
  platform_id?: string;
  trace_id?: string;
}): Promise<{ success: boolean; filename: string; report_path: string; is_html: boolean } | null> {
  const res = await apiPost<{ success: boolean; filename: string; report_path: string; is_html: boolean }>(
    "reports/rerender",
    params
  );
  return extractData(res) || null;
}

export interface TemplateInstallResult {
  name: string;
  label: string;
  desc?: string;
  has_image: boolean;
  has_html: boolean;
  files: string[];
}

function assertInstallResult(
  res: unknown,
  fallback: string
): TemplateInstallResult | null {
  // extractData 会把顶层错误响应（如 {status:"error", message}）直接造型为结果，
  // 这里显式校验：必须是含 name 的安装结果，否则按失败处理并透传后端错误信息。
  if (!res || typeof res !== "object") return null;
  const obj = res as Record<string, unknown>;
  let candidate: unknown = obj;
  // 兼容标准的 json_response 双层包装：{data:{data:{name...}}} 与单层 {data:{name...}}
  for (let i = 0; i < 2; i += 1) {
    const inner = candidate as Record<string, unknown> | null;
    if (inner && "data" in inner) {
      candidate = inner.data;
    } else {
      break;
    }
  }
  if (
    candidate &&
    typeof candidate === "object" &&
    typeof (candidate as Record<string, unknown>).name === "string"
  ) {
    return candidate as unknown as TemplateInstallResult;
  }
  const msg = typeof obj.message === "string" && obj.message ? obj.message : fallback;
  throw new Error(msg);
}

export async function installTemplateFromUrl(params: {
  repo_url: string;
  name?: string;
}): Promise<TemplateInstallResult | null> {
  const res = await apiPost<TemplateInstallResult>(`templates/install_from_url`, params);
  return assertInstallResult(res, "安装失败，请检查链接或服务器日志。");
}

export async function installTemplateFromFile(
  file: File,
  name?: string
): Promise<TemplateInstallResult | null> {
  const base64Data = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = (e) => reject(e);
    reader.readAsDataURL(file);
  });
  const res = await apiPost<TemplateInstallResult>(`templates/install_from_file`, {
    filename: file.name,
    file_data: base64Data,
    name: name || undefined,
  });
  return assertInstallResult(res, "安装失败，请确认压缩包内包含 image_template.html。");
}

