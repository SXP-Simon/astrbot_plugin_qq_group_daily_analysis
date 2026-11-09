import { useCallback, useEffect, useRef, type ReactNode } from "react";
import { IconAlertCircle, IconPlus, IconRefresh } from "@tabler/icons-react";
import logo from "@/shared/assets/logo.png";
import { Button } from "@/shared/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";

interface AppShellProps {
  activePage: string;
  visited: ReadonlySet<string>;
  items: { key: string; label: string; icon: ReactNode; children: ReactNode }[];
  onNavigate: (page: string) => void;
  onRefresh: () => void;
  onOpenTrigger: () => void;
  loading: boolean;
  configDirty?: boolean;
}

export function AppShell({
  activePage,
  visited,
  items,
  onNavigate,
  onRefresh,
  onOpenTrigger,
  loading,
  configDirty = false,
}: AppShellProps) {
  const navigation = useRef<HTMLDivElement>(null);
  const scrollFrame = useRef<number | null>(null);
  const centerSelected = useCallback(() => {
    if (scrollFrame.current !== null) cancelAnimationFrame(scrollFrame.current);
    scrollFrame.current = requestAnimationFrame(() => {
      scrollFrame.current = null;
      const container = navigation.current;
      const selected = container?.querySelector<HTMLElement>('[aria-selected="true"]');
      if (!selected || !container) return;
      // 使用相对几何位置，只滚动导航横轴，不干扰页面已恢复的滚动位置。
      const left =
        container.scrollLeft +
        selected.getBoundingClientRect().left -
        container.getBoundingClientRect().left +
        selected.offsetWidth / 2 -
        container.clientWidth / 2;
      const target = Math.max(0, Math.min(container.scrollWidth - container.clientWidth, left));
      if (Math.abs(target - container.scrollLeft) < 1) return;
      container.scrollTo({
        left: target,
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      });
    });
  }, []);
  useEffect(() => {
    centerSelected();
    return () => {
      if (scrollFrame.current !== null) cancelAnimationFrame(scrollFrame.current);
    };
  }, [activePage, centerSelected]);
  useEffect(() => {
    const container = navigation.current;
    if (!container) return;
    const observer = new ResizeObserver(centerSelected);
    observer.observe(container);
    const onWheel = (event: WheelEvent) => {
      if (
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.deltaX !== 0 ||
        !event.cancelable
      )
        return;
      const max = container.scrollWidth - container.clientWidth;
      if (
        max <= 0 ||
        (event.deltaY < 0 && container.scrollLeft <= 1) ||
        (event.deltaY > 0 && container.scrollLeft >= max - 1)
      )
        return;
      const unit =
        event.deltaMode === WheelEvent.DOM_DELTA_LINE
          ? parseFloat(getComputedStyle(container).lineHeight) || 16
          : event.deltaMode === WheelEvent.DOM_DELTA_PAGE
            ? container.clientWidth
            : 1;
      const left = Math.max(0, Math.min(max, container.scrollLeft + event.deltaY * unit));
      if (left === container.scrollLeft) return;
      if (scrollFrame.current !== null) cancelAnimationFrame(scrollFrame.current);
      scrollFrame.current = null;
      event.preventDefault();
      container.scrollLeft = left;
    };
    container.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      observer.disconnect();
      container.removeEventListener("wheel", onWheel);
      if (scrollFrame.current !== null) cancelAnimationFrame(scrollFrame.current);
    };
  }, [centerSelected]);

  return (
    <Tabs value={activePage} onValueChange={onNavigate} className="app-shell">
      <a className="skip-link" href="#page-content">
        跳到页面内容
      </a>
      <header className="app-header">
        <div className="app-brand">
          <img
            src={logo}
            alt="AstrBot 群分析总结插件"
            className="size-8 rounded-lg object-contain"
          />
          <span>AstrBot 群分析总结插件</span>
        </div>
        <div className="app-navigation" ref={navigation} onClick={centerSelected}>
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
        {configDirty && activePage !== "config" && (
          <div
            role="status"
            aria-label="配置未保存提醒"
            className="sticky top-2 z-20 mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-solid border-warning/30 bg-[color-mix(in_srgb,var(--warning)_10%,var(--background))] px-4 py-2 text-warning"
          >
            <span className="flex items-center gap-2 text-sm">
              <IconAlertCircle className="size-4 shrink-0" aria-hidden="true" />
              配置有未保存的修改
            </span>
            <Button variant="outline" size="sm" onClick={() => onNavigate("config")}>
              返回配置
            </Button>
          </div>
        )}
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
