import { IconRefresh } from "@tabler/icons-react";
import { Button } from "../../../../shared/ui/button";
import { Input } from "../../../../shared/ui/input";
import { NativeSelect } from "../../../../shared/ui/native-select";
import { formatStageName } from "../../../../shared/lib/formatters";
import type { usePluginDataViewModel } from "../../model/usePluginDataViewModel";

export function CheckpointFilterBar({ vm }: { vm: ReturnType<typeof usePluginDataViewModel> }) {
  const stages = [
    ...new Set([
      "FETCH_MESSAGES",
      "CLEAN_MESSAGES",
      "STATS_ANALYSIS",
      "LLM_ANALYSIS",
      "SAVE_SUMMARY",
      "RENDER_REPORT",
      "DISPATCH_REPORT",
      "COMIC_STORYBOARD",
      "COMIC_DRAWING",
      ...vm.checkpoints.map((item) => item.stage_name),
      ...(vm.ckptFilterStage ? [vm.ckptFilterStage] : []),
    ]),
  ];
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid w-64 max-w-full gap-1 text-sm">
          群聊
          <NativeSelect
            value={vm.ckptFilterGroup || ""}
            onChange={(event) =>
              void vm.loadCheckpoints({ page: 1, group: event.target.value || undefined })
            }
          >
            <option value="">全部群聊</option>
            {[
              ...new Set([...vm.ckptGroups, ...(vm.ckptFilterGroup ? [vm.ckptFilterGroup] : [])]),
            ].map((group) => (
              <option key={group} value={group}>
                {group}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="grid w-48 max-w-full gap-1 text-sm">
          分析归属日期
          <Input
            type="date"
            value={vm.ckptFilterDate || ""}
            onChange={(event) =>
              void vm.loadCheckpoints({ page: 1, date: event.target.value || undefined })
            }
          />
        </label>
        <label className="grid w-64 max-w-full gap-1 text-sm">
          阶段
          <NativeSelect
            value={vm.ckptFilterStage || ""}
            onChange={(event) =>
              void vm.loadCheckpoints({ page: 1, stage: event.target.value || undefined })
            }
          >
            <option value="">全部阶段</option>
            {stages.map((stage) => (
              <option key={stage} value={stage}>
                {formatStageName(stage)} · {stage}
              </option>
            ))}
          </NativeSelect>
        </label>
        <Button
          variant="ghost"
          onClick={() =>
            void vm.loadCheckpoints({
              page: 1,
              group: undefined,
              date: undefined,
              stage: undefined,
            })
          }
        >
          清空筛选
        </Button>
        <Button
          variant="outline"
          disabled={vm.loadingCheckpoints}
          onClick={() => {
            void vm.refreshCheckpointGroups();
            void vm.loadCheckpoints();
          }}
        >
          <IconRefresh aria-hidden="true" className={vm.loadingCheckpoints ? "animate-spin" : ""} />
          刷新
        </Button>
      </div>
      {vm.checkpointGroupsError && (
        <p role="alert" className="m-0 text-sm text-warning">
          {vm.checkpointGroupsError}
        </p>
      )}
    </div>
  );
}
