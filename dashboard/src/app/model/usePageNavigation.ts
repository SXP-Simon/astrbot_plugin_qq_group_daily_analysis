import { useLayoutEffect, useRef, useState } from "react";

/** 页面保持挂载以保留编辑值；切换只恢复本页滚动，不生成整页动画快照。 */
export function usePageNavigation(initialPage: string) {
  const [page, setPage] = useState(initialPage);
  const [visited, setVisited] = useState(() => new Set([initialPage]));
  const current = useRef(initialPage);
  const positions = useRef(new Map<string, number>());
  const changed = useRef(false);

  const navigate = (next: string) => {
    if (next === current.current) return;
    positions.current.set(current.current, window.scrollY);
    current.current = next;
    changed.current = true;
    setVisited((previous) => new Set([...previous, next]));
    setPage(next);
  };

  useLayoutEffect(() => {
    if (!changed.current) return;
    changed.current = false;
    window.scrollTo({ top: positions.current.get(page) ?? 0, behavior: "instant" });
  }, [page]);

  return { page, visited, navigate };
}
