import type { AnalyticsTrendPoint, ProviderBreakdownItem } from "../../entities/metric/model/types";

export function TrendDataTables({
  points,
  providers,
  rangeLabel,
}: {
  points: AnalyticsTrendPoint[];
  providers: ProviderBreakdownItem[];
  rangeLabel: string;
}) {
  const total = providers.reduce((sum, item) => sum + item.total_tokens, 0);
  return (
    <div className="mt-4 space-y-3 text-sm">
      <details>
        <summary className="w-fit cursor-pointer rounded-md text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring">
          查看趋势明细
        </summary>
        <div
          className="mt-3 overflow-x-auto rounded-lg border border-solid border-border"
          role="region"
          aria-label="趋势明细"
          tabIndex={0}
        >
          <table className="w-full min-w-[650px] border-collapse text-left text-sm">
            <caption className="p-3 text-left">{rangeLabel} · 分析次数与模型消耗</caption>
            <thead className="bg-secondary">
              <tr>
                {["时间", "分析", "成功", "失败", "输入 Tokens", "输出 Tokens", "总 Tokens"].map(
                  (label) => (
                    <th key={label} scope="col" className="px-3 py-2 font-medium">
                      {label}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.timestamp}>
                  <th scope="row" className="whitespace-nowrap px-3 py-2 font-normal">
                    {point.date_full}
                  </th>
                  {[
                    point.request_count,
                    point.succeeded_count,
                    point.failed_count,
                    point.prompt_tokens,
                    point.completion_tokens,
                    point.total_tokens,
                  ].map((value, index) => (
                    <td key={index} className="px-3 py-2 tabular-nums">
                      {value.toLocaleString()}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {!points.length && <p className="px-3">此范围暂无记录</p>}
        </div>
      </details>
      <details>
        <summary className="w-fit cursor-pointer rounded-md text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring">
          查看服务商明细
        </summary>
        <div
          className="mt-3 overflow-x-auto rounded-lg border border-solid border-border"
          role="region"
          aria-label="服务商明细"
          tabIndex={0}
        >
          <table className="w-full min-w-[420px] border-collapse text-left text-sm">
            <caption className="p-3 text-left">{rangeLabel} · 全部服务商</caption>
            <thead className="bg-secondary">
              <tr>
                {["服务商", "分析次数", "Tokens", "消耗占比"].map((label) => (
                  <th key={label} scope="col" className="px-3 py-2 font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {providers.map((item, index) => (
                <tr key={`${item.name}-${index}`}>
                  <th scope="row" className="break-all px-3 py-2 font-normal">
                    {item.name}
                  </th>
                  <td className="px-3 py-2 tabular-nums">{item.request_count.toLocaleString()}</td>
                  <td className="px-3 py-2 tabular-nums">{item.total_tokens.toLocaleString()}</td>
                  <td className="px-3 py-2 tabular-nums">
                    {total > 0
                      ? `${((item.total_tokens / total) * 100).toFixed(1)}%`
                      : "未记录消耗"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!providers.length && <p className="px-3">此范围暂无服务商记录</p>}
        </div>
      </details>
    </div>
  );
}
