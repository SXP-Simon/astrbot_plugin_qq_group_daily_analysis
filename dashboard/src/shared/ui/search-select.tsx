import { useEffect, useId, useRef, useState } from "react";
import { IconCheck, IconChevronDown } from "@tabler/icons-react";
import { Button } from "./button";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "./dialog";
import { Input } from "./input";

interface SearchSelectProps {
  label: string;
  value: string;
  options: { value: string; label: string; searchText?: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
  virtual?: boolean;
}

export function SearchSelect({
  label,
  value,
  options,
  onChange,
  disabled,
  virtual = false,
}: SearchSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const id = useId();
  const viewport = useRef<HTMLDivElement>(null);
  const [scrollOffset, setScrollOffset] = useState(0);
  const [activeValue, setActiveValue] = useState<string | null>(null);
  const selected = options.find((option) => option.value === value);
  const matches = options.filter((option) =>
    `${option.label} ${option.value} ${option.searchText || ""}`
      .toLocaleLowerCase()
      .includes(search.trim().toLocaleLowerCase()),
  );
  // 活动项跟随稳定的值；后台元数据导致排序变化时，Enter 不能选中相同索引下的另一个模板。
  const activeIndex = matches.findIndex((option) => option.value === activeValue);
  const keyboardChoice = activeValue === null ? matches[0] : matches[activeIndex];
  // 固定行高只用于大量选项；普通群聊选择保留原有的自然换行布局。
  const rowHeight = 56;
  const start = virtual ? Math.max(0, Math.floor(scrollOffset / rowHeight) - 2) : 0;
  const end = virtual ? Math.min(matches.length, start + 11) : matches.length;
  useEffect(() => {
    const list = viewport.current;
    if (!virtual || !open || !list || activeIndex < 0) return;
    const top = activeIndex * rowHeight;
    const height = list.clientHeight || 320;
    const next =
      top < list.scrollTop
        ? top
        : top + rowHeight > list.scrollTop + height
          ? top + rowHeight - height
          : list.scrollTop;
    list.scrollTop = next;
    setScrollOffset(next);
  }, [activeIndex, open, virtual]);
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next && disabled) return;
        setOpen(next);
        setSearch("");
        setScrollOffset(0);
        setActiveValue(
          next ? (options.find((option) => option.value === value)?.value ?? null) : null,
        );
      }}
    >
      <DialogTrigger asChild>
        <Button
          variant="outline"
          disabled={disabled}
          aria-label={`${label}：${selected?.label ?? (value || "请选择")}`}
          className="w-full min-w-0 max-w-full justify-between text-left"
        >
          <span className="truncate">{selected?.label ?? (value || "请选择")}</span>
          <IconChevronDown aria-hidden="true" />
        </Button>
      </DialogTrigger>
      <DialogContent
        aria-describedby={undefined}
        onEscapeKeyDown={(event) => event.stopPropagation()}
      >
        <DialogTitle>{label}</DialogTitle>
        <label htmlFor={id} className="sr-only">
          搜索{label}
        </label>
        <Input
          id={id}
          type="search"
          role={virtual ? "combobox" : undefined}
          aria-expanded={virtual ? open : undefined}
          aria-autocomplete={virtual ? "list" : undefined}
          aria-controls={virtual ? `${id}-options` : undefined}
          aria-activedescendant={
            virtual && activeIndex >= start && activeIndex < end
              ? `${id}-${activeIndex}`
              : undefined
          }
          disabled={disabled}
          value={search}
          placeholder="输入名称或编号"
          onChange={(event) => {
            setSearch(event.target.value);
            setActiveValue(null);
            setScrollOffset(0);
            if (viewport.current) viewport.current.scrollTop = 0;
          }}
          onKeyDown={(event) => {
            if (!virtual || disabled || !matches.length) return;
            if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
              event.preventDefault();
              setActiveValue((current) => {
                const index = matches.findIndex((option) => option.value === current);
                const next =
                  event.key === "Home"
                    ? 0
                    : event.key === "End"
                      ? matches.length - 1
                      : event.key === "ArrowDown"
                        ? Math.min(matches.length - 1, index + 1)
                        : Math.max(0, index - 1);
                return matches[next]?.value ?? null;
              });
            } else if (event.key === "Enter" && keyboardChoice) {
              event.preventDefault();
              onChange(keyboardChoice.value);
              setOpen(false);
              setSearch("");
            }
          }}
        />
        <div
          ref={viewport}
          className={virtual ? "h-80 overflow-auto" : "max-h-80 overflow-auto"}
          aria-label={`${label}选项`}
          onScroll={virtual ? (event) => setScrollOffset(event.currentTarget.scrollTop) : undefined}
        >
          {matches.length === 0 ? (
            <p role="status" className="text-sm text-muted-foreground">
              没有匹配的选项
            </p>
          ) : (
            <ul
              id={`${id}-options`}
              role={virtual ? "listbox" : undefined}
              aria-label={virtual ? `${label}选项` : undefined}
              className={virtual ? "relative m-0 list-none p-0" : "m-0 list-none space-y-1 p-0"}
              style={virtual ? { height: matches.length * rowHeight } : undefined}
            >
              {matches.slice(start, end).map((option, offset) => (
                <li
                  key={option.value}
                  role={virtual ? "presentation" : undefined}
                  style={
                    virtual
                      ? {
                          position: "absolute",
                          top: (start + offset) * rowHeight,
                          height: rowHeight,
                          width: "100%",
                        }
                      : undefined
                  }
                >
                  <Button
                    variant={value === option.value ? "secondary" : "ghost"}
                    id={`${id}-${start + offset}`}
                    role={virtual ? "option" : undefined}
                    tabIndex={virtual ? -1 : undefined}
                    aria-selected={virtual ? value === option.value : undefined}
                    aria-posinset={virtual ? start + offset + 1 : undefined}
                    aria-setsize={virtual ? matches.length : undefined}
                    aria-pressed={virtual ? undefined : value === option.value}
                    disabled={disabled}
                    title={virtual ? option.label : undefined}
                    className={
                      virtual
                        ? `h-14 w-full justify-between whitespace-normal text-left ${start + offset === activeIndex ? "bg-accent" : ""}`
                        : "h-auto min-h-10 w-full justify-between whitespace-normal text-left"
                    }
                    onClick={() => {
                      onChange(option.value);
                      setOpen(false);
                      setSearch("");
                    }}
                  >
                    <span className={virtual ? "line-clamp-2 break-words" : "break-words"}>
                      {option.label}
                    </span>
                    {value === option.value && <IconCheck aria-hidden="true" />}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
