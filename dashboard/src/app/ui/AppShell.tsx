import { useEffect, useRef, type ReactNode } from "react";
import { IconStack2, IconPlus, IconRefresh } from "@tabler/icons-react";
import { Button } from "../../shared/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../shared/ui/tabs";

interface AppShellProps {
  activePage: string;
  visited: ReadonlySet<string>;
  items: { key: string; label: string; icon: ReactNode; children: ReactNode }[];
  onNavigate: (page: string) => void;
  onRefresh: () => void;
  onOpenTrigger: () => void;
  loading: boolean;
}

export function AppShell({
  activePage,
  visited,
  items,
  onNavigate,
  onRefresh,
  onOpenTrigger,
  loading,
}: AppShellProps) {
  const navigation = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const selected = navigation.current?.querySelector<HTMLElement>('[aria-selected="true"]');
    const container = navigation.current;
    if (!selected || !container) return;
    // 只滚动导航自己的横轴，不能把已恢复的页面位置滚回顶部。
    const left = selected.offsetLeft - container.offsetLeft;
    if (left < container.scrollLeft) container.scrollLeft = left;
    else if (left + selected.offsetWidth > container.scrollLeft + container.clientWidth)
      container.scrollLeft = left + selected.offsetWidth - container.clientWidth;
  }, [activePage]);

  return (
    <Tabs value={activePage} onValueChange={onNavigate} className="app-shell">
      <a className="skip-link" href="#page-content">
        跳到页面内容
      </a>
      <header className="app-header">
        <div className="app-brand">
          <IconStack2 size={23} aria-hidden="true" />
          <span>群聊分析</span>
        </div>
        <div className="app-navigation" ref={navigation}>
          <TabsList aria-label="主导航" className="bg-transparent p-0">
            {items.map((item) => (
              <TabsTrigger key={item.key} value={item.key} className="rounded-xl px-3 py-2 text-sm">
                {item.icon}
                <span>{item.label}</span>
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
      </header>
      <main id="page-content" tabIndex={-1} className="app-main">
        <div className="page-heading">
          <h1>{items.find((item) => item.key === activePage)?.label}</h1>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={onRefresh}
              aria-label="刷新数据"
              title="刷新数据"
              aria-busy={loading}
            >
              <IconRefresh className={loading ? "animate-spin" : undefined} aria-hidden="true" />
            </Button>
            <Button onClick={onOpenTrigger}>
              <IconPlus aria-hidden="true" />
              发起分析
            </Button>
          </div>
        </div>
        {items
          .filter((item) => visited.has(item.key))
          .map((item) => (
            <TabsContent
              key={item.key}
              value={item.key}
              forceMount
              hidden={activePage !== item.key}
              className="page-content mt-0"
            >
              {item.children}
            </TabsContent>
          ))}
      </main>
    </Tabs>
  );
}
