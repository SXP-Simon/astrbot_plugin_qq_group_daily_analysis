import type { GroupItem } from "@/entities/group/model/types";
import { NativeSelect } from "@/shared/ui/native-select";
import { SearchSelect } from "@/shared/ui/search-select";

interface GroupFiltersProps {
  groups: GroupItem[];
  selectedPlatform?: string;
  selectedGroup?: string;
  onPlatformChange?: (platform?: string) => void;
  onGroupChange: (groupId?: string, platform?: string) => void;
}

const PLATFORM_NAMES: Record<string, string> = {
  aiocqhttp: "OneBot v11",
  qq_official: "QQ 官方机器人",
  qq_official_webhook: "QQ 官方 Webhook",
  telegram: "Telegram",
  discord: "Discord",
  satori: "Satori",
  "": "未记录平台",
};

export function GroupFilters({
  groups,
  selectedPlatform,
  selectedGroup,
  onPlatformChange,
  onGroupChange,
}: GroupFiltersProps) {
  const platforms = [...new Set(groups.map((group) => group.platform))];
  if (selectedPlatform !== undefined && !platforms.includes(selectedPlatform))
    platforms.push(selectedPlatform);
  const visible = groups.filter(
    (group) => selectedPlatform === undefined || group.platform === selectedPlatform,
  );
  const groupOptions = [
    ...new Map(
      visible.map((group) => {
        const value = JSON.stringify([group.platform, group.group_id]);
        const name =
          group.group_name && group.group_name !== group.group_id ? group.group_name : "未记录群名";
        return [
          value,
          {
            value,
            label: `${name}（${group.group_id}）${selectedPlatform === undefined ? ` · ${PLATFORM_NAMES[group.platform] ?? group.platform}` : ""}`,
          },
        ];
      }),
    ).values(),
  ];
  const value = selectedGroup ? JSON.stringify([selectedPlatform ?? null, selectedGroup]) : "";
  if (selectedGroup && !groupOptions.some((option) => option.value === value)) {
    groupOptions.push({
      value,
      label: `${selectedGroup} · ${selectedPlatform === undefined ? "全部平台" : "当前筛选"}`,
    });
  }
  return (
    <>
      <label className="grid min-w-0 gap-1 text-sm text-muted-foreground">
        平台
        <NativeSelect
          disabled={!onPlatformChange}
          value={selectedPlatform === undefined ? "" : JSON.stringify(selectedPlatform)}
          onChange={(event) => {
            const platform = platforms.find((item) => JSON.stringify(item) === event.target.value);
            onPlatformChange?.(platform);
          }}
        >
          <option value="">全部平台</option>
          {platforms.map((platform) => (
            <option key={platform} value={JSON.stringify(platform)}>
              {PLATFORM_NAMES[platform] ?? platform}
            </option>
          ))}
        </NativeSelect>
      </label>
      <div className="grid min-w-0 gap-1 text-sm text-muted-foreground">
        <span>群聊</span>
        <SearchSelect
          label="选择群聊"
          value={value}
          options={[{ value: "", label: "全部群聊" }, ...groupOptions]}
          onChange={(next) => {
            if (!next) {
              onGroupChange(undefined, selectedPlatform);
              return;
            }
            const group = visible.find(
              (item) => JSON.stringify([item.platform, item.group_id]) === next,
            );
            if (group) onGroupChange(group.group_id, group.platform);
          }}
        />
      </div>
    </>
  );
}
