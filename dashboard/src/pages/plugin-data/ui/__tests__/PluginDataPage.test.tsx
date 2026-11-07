import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { PluginDataPage } from "../PluginDataPage";
import type { FontManagementRequest } from "../../../../features/manage-typst-fonts/model/FontManagementContext";
import {
  fetchIncrementalGroupDirectory,
  fetchCheckpointGroups,
  fetchCheckpointsList,
} from "../../../../entities/plugin-data/api/pluginDataApi";

vi.mock("../../../../entities/plugin-data/api/pluginDataApi");
vi.mock("../partitions/ManagedFilesPanel", () => ({
  ManagedFilesPanel: ({
    onOpenDataTab,
    fontRequest,
  }: {
    onOpenDataTab: (value: string) => void;
    fontRequest?: FontManagementRequest | null;
  }) => (
    <div>
      存储概览内容 {fontRequest?.theme}
      <button onClick={() => onOpenDataTab("records")}>查看存档</button>
    </div>
  ),
}));
vi.mock("../StoredRecordsTab", () => ({ StoredRecordsTab: () => <div>分析存档内容</div> }));
vi.mock("../incremental/IncrementalTab", () => ({ IncrementalTab: () => <div>增量批次内容</div> }));
vi.mock("../checkpoints/CheckpointsTab", () => ({ CheckpointsTab: () => <div>阶段快照内容</div> }));
vi.mock("../incremental/BatchDetailModal", () => ({ BatchDetailModal: () => null }));
vi.mock("../checkpoints/CheckpointDetailModal", () => ({ CheckpointDetailModal: () => null }));
beforeEach(() => {
  vi.mocked(fetchIncrementalGroupDirectory).mockResolvedValue({ groups: [], group_details: [] });
  vi.mocked(fetchCheckpointGroups).mockResolvedValue([]);
  vi.mocked(fetchCheckpointsList).mockResolvedValue({ items: [], total: 0 });
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it("数据分区支持键盘切换，离开后卸载旧内容并保留存档入口", async () => {
  await act(async () => {
    render(<PluginDataPage />);
  });
  const first = screen.getByRole("tab", { name: "存储空间概览" });
  act(() => first.focus());
  fireEvent.keyDown(first, { key: "ArrowRight" });
  await waitFor(() =>
    expect(screen.getByRole("tab", { name: "分析存档与头像" })).toHaveAttribute(
      "aria-selected",
      "true",
    ),
  );
  expect(screen.getByRole("tabpanel")).toHaveTextContent("分析存档内容");
  expect(screen.queryByText("存储概览内容")).not.toBeInTheDocument();
  await act(async () => {
    fireEvent.mouseDown(screen.getByRole("tab", { name: "阶段产物快照" }), {
      button: 0,
      ctrlKey: false,
    });
  });
  expect(screen.getByRole("tabpanel")).toHaveTextContent("阶段快照内容");
  fireEvent.mouseDown(first, { button: 0, ctrlKey: false });
  fireEvent.click(screen.getByRole("button", { name: "查看存档" }));
  expect(screen.getByRole("tabpanel")).toHaveTextContent("分析存档内容");
});

it("跨页字体管理请求仍返回存储分区并带上主题", async () => {
  const { rerender } = render(<PluginDataPage />);
  await act(async () => {});
  fireEvent.mouseDown(screen.getByRole("tab", { name: "增量分析批次" }), {
    button: 0,
    ctrlKey: false,
  });
  expect(screen.getByRole("tabpanel")).toHaveTextContent("增量批次内容");
  rerender(
    <PluginDataPage
      fontRequest={{
        sequence: 1,
        theme: "HatsuneMiku",
        cdnBaseUrl: "https://cdn.example",
        source: "cdn",
      }}
    />,
  );
  await waitFor(() =>
    expect(screen.getByRole("tab", { name: "存储空间概览" })).toHaveAttribute(
      "aria-selected",
      "true",
    ),
  );
  expect(screen.getByRole("tabpanel")).toHaveTextContent("HatsuneMiku");
});
