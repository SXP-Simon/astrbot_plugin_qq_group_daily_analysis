import { IconChevronLeft, IconChevronRight } from "@tabler/icons-react";
import { Button } from "./button";
import { NativeSelect } from "./native-select";
import { Fragment } from "react";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  pageSizes?: number[];
  disabled?: boolean;
  onChange: (page: number, pageSize: number) => void;
}

export function Pagination({
  page,
  pageSize,
  total,
  pageSizes = [10, 15, 20, 50, 100],
  disabled = false,
  onChange,
}: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const visiblePages = [...new Set([1, page - 1, page, page + 1, pages])]
    .filter((value) => value >= 1 && value <= pages)
    .sort((a, b) => a - b);
  return (
    <nav
      aria-label="分页"
      className="flex flex-wrap items-center justify-between gap-3 py-4 text-sm"
    >
      <span className="text-muted-foreground">共 {total.toLocaleString()} 条记录</span>
      <div className="flex flex-wrap items-center gap-2">
        <div className="w-28">
          <NativeSelect
            aria-label="每页条数"
            value={pageSize}
            disabled={disabled}
            onChange={(event) => onChange(1, Number(event.target.value))}
          >
            {[...new Set([...pageSizes, pageSize])]
              .sort((a, b) => a - b)
              .map((size) => (
                <option key={size} value={size}>
                  {size} 条 / 页
                </option>
              ))}
          </NativeSelect>
        </div>
        <Button
          variant="outline"
          size="icon"
          aria-label="上一页"
          disabled={disabled || page <= 1}
          onClick={() => onChange(page - 1, pageSize)}
        >
          <IconChevronLeft aria-hidden="true" />
        </Button>
        {visiblePages.map((value, index) => (
          <Fragment key={value}>
            {index > 0 && value - visiblePages[index - 1] > 1 && <span aria-hidden="true">…</span>}
            <Button
              size="icon"
              variant={value === page ? "secondary" : "ghost"}
              aria-label={`第 ${value} 页`}
              aria-current={value === page ? "page" : undefined}
              disabled={disabled}
              onClick={() => {
                if (value !== page) onChange(value, pageSize);
              }}
            >
              {value}
            </Button>
          </Fragment>
        ))}
        <Button
          variant="outline"
          size="icon"
          aria-label="下一页"
          disabled={disabled || page >= pages}
          onClick={() => onChange(page + 1, pageSize)}
        >
          <IconChevronRight aria-hidden="true" />
        </Button>
      </div>
    </nav>
  );
}
