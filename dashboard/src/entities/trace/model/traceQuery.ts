export type TraceSortField = "started_at" | "duration_ms" | "total_tokens" | "compression_ratio";
export type TraceSortOrder = "asc" | "desc";

export interface TraceQuery {
  page: number;
  pageSize: number;
  search: string;
  statusFilter?: string;
  triggerTypeFilter?: string;
  selectedGroup?: string;
  selectedPlatform?: string;
  dateRange: [number, number] | null;
  sortField: TraceSortField;
  sortOrder: TraceSortOrder;
}
