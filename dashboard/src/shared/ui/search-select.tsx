import { useId, useState } from "react";
import { IconCheck, IconChevronDown } from "@tabler/icons-react";
import { Button } from "./button";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "./dialog";
import { Input } from "./input";

interface SearchSelectProps {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function SearchSelect({ label, value, options, onChange, disabled }: SearchSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const id = useId();
  const selected = options.find((option) => option.value === value);
  const matches = options.filter((option) =>
    `${option.label} ${option.value}`
      .toLocaleLowerCase()
      .includes(search.trim().toLocaleLowerCase()),
  );
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setSearch("");
      }}
    >
      <DialogTrigger asChild>
        <Button
          variant="outline"
          disabled={disabled}
          aria-label={`${label}：${selected?.label ?? (value || "请选择")}`}
          className="w-full justify-between text-left"
        >
          <span className="truncate">{selected?.label ?? (value || "请选择")}</span>
          <IconChevronDown aria-hidden="true" />
        </Button>
      </DialogTrigger>
      <DialogContent aria-describedby={undefined}>
        <DialogTitle>{label}</DialogTitle>
        <label htmlFor={id} className="sr-only">
          搜索{label}
        </label>
        <Input
          id={id}
          type="search"
          value={search}
          placeholder="输入名称或编号"
          onChange={(event) => setSearch(event.target.value)}
        />
        <div className="max-h-80 overflow-auto" aria-label={`${label}选项`}>
          {matches.length === 0 ? (
            <p role="status" className="text-sm text-muted-foreground">
              没有匹配的选项
            </p>
          ) : (
            <ul className="m-0 list-none space-y-1 p-0">
              {matches.map((option) => (
                <li key={option.value}>
                  <Button
                    variant={value === option.value ? "secondary" : "ghost"}
                    aria-pressed={value === option.value}
                    className="h-auto min-h-10 w-full justify-between whitespace-normal text-left"
                    onClick={() => {
                      onChange(option.value);
                      setOpen(false);
                      setSearch("");
                    }}
                  >
                    <span className="break-words">{option.label}</span>
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
