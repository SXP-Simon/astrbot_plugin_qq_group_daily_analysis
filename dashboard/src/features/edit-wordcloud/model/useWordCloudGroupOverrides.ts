import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchDistinctGroups } from "../../../entities/group/api/groupApi";
import type { GroupItem } from "../../../entities/group/model/types";
import { useWordCloudCatalog } from "./useWordCloudCatalog";
import { buildOverrideGroupOptions, getEffectiveWordCloud, getOverrideErrors, isGroupUmo, isOverrideRecord, setOverrideFields, updateGroupOverride, WORDCLOUD_OVERRIDE_FIELDS, type WordCloudOverrideField } from "./wordCloudGroupOverrides";

export interface WordCloudGroupOverridesProps {
  value?: unknown;
  globalValue?: Record<string, unknown>;
  disabled?: boolean;
  active?: boolean;
  catalogRevision?: number;
  onChange: (value: Record<string, unknown>) => void;
  onEditAppearance?: (umo: string) => void;
}

export function useWordCloudGroupOverrides({ value, globalValue = {}, disabled = false, active = true, catalogRevision = 0, onChange }: WordCloudGroupOverridesProps) {
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState("");
  const [manualUmo, setManualUmo] = useState("");
  const [manualError, setManualError] = useState("");
  const refresh = useCallback(() => setRevision((previous) => previous + 1), []);
  useEffect(() => {
    if (!active) return;
    let current = true;
    setLoading(true);
    setLoadError("");
    fetchDistinctGroups(revision > 0).then((next) => { if (current) setGroups(next); })
      .catch((reason: unknown) => { if (current) setLoadError(reason instanceof Error ? reason.message : "读取群列表失败"); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [active, revision]);

  const overrides = useMemo(() => isOverrideRecord(value) ? value : {}, [value]);
  const malformed = value !== undefined && !isOverrideRecord(value);
  const selectedValue = overrides[selected];
  const invalidGroup = selectedValue !== undefined && !isOverrideRecord(selectedValue);
  const override = isOverrideRecord(selectedValue) ? selectedValue : {};
  const effective = getEffectiveWordCloud(globalValue, override);
  const selectedKeys = WORDCLOUD_OVERRIDE_FIELDS.filter(({ key }) => Object.prototype.hasOwnProperty.call(override, key)).map(({ key }) => key);
  const errors = getOverrideErrors(globalValue, override);
  const options = buildOverrideGroupOptions(groups, overrides);
  if (selected && !options.some((option) => option.value === selected)) options.push({ value: selected, label: selected });
  const catalog = useWordCloudCatalog({ active: active && !!selected, revision: catalogRevision, template: String(effective.template), font: String(effective.font) });
  const locked = disabled || malformed || invalidGroup || !selected;
  const setFields = (keys: WordCloudOverrideField[]) => { if (!locked) onChange(setOverrideFields(overrides, selected, keys, globalValue)); };
  const update = (key: WordCloudOverrideField, next: unknown) => { if (!locked) onChange(updateGroupOverride(overrides, selected, key, next)); };
  const selectManual = () => {
    const next = manualUmo.trim();
    if (!isGroupUmo(next)) {
      setManualError("请填写 /sid 返回的完整群会话标识，例如 bot:GroupMessage:123456。");
      return;
    }
    setSelected(next);
    setManualUmo("");
    setManualError("");
  };

  return { options, loading, loadError, refresh, selected, setSelected, manualUmo, setManualUmo, manualError, selectManual, malformed, invalidGroup, effective, selectedKeys, errors, catalog, locked, setFields, update };
}
