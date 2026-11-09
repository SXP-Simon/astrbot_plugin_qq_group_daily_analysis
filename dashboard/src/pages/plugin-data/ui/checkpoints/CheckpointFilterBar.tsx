import { GroupFilters } from "@/entities/group/ui/GroupFilters";
import { IconRefresh } from "@tabler/icons-react";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { NativeSelect } from "@/shared/ui/native-select";
import { formatStageName } from "@/shared/lib/formatters";
import type { usePluginDataViewModel } from "@/pages/plugin-data/model/usePluginDataViewModel";

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
        <div className="grid w-full gap-3 sm:w-[36rem] sm:grid-cols-[1fr_2fr]">
          <GroupFilters
            groups={vm.ckptGroups}
            selectedGroup={vm.ckptFilterGroup}
            selectedPlatform={vm.ckptFilterPlatform}
            onPlatformChange={(platform) =>
              void vm.loadCheckpoints({ page: 1, platform, group: undefined })
            }
            onGroupChange={(group, platform) =>
              void vm.loadCheckpoints({ page: 1, group, platform })
            }
          />
        </div>
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
              platform: undefined,
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
