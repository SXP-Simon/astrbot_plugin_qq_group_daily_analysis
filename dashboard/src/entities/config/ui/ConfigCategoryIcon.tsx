import {
  IconAdjustmentsHorizontal,
  IconRobot,
  IconPhoto,
  IconCalendarClock,
  IconBrain,
  IconChartBar,
  IconPalette,
  IconRefresh,
  IconCode,
  IconCloudUpload,
  IconMessage,
  IconGauge,
  type Icon,
} from "@tabler/icons-react";

// 图标只辅助识别分组，名称与说明继续由原始配置 Schema 提供。
const categoryIcons: Record<string, Icon> = {
  basic: IconAdjustmentsHorizontal,
  qq_official: IconRobot,
  t2i_rendering: IconPhoto,
  auto_analysis: IconCalendarClock,
  llm: IconBrain,
  analysis_features: IconChartBar,
  daily_comic: IconPalette,
  incremental: IconRefresh,
  html: IconCode,
  qq_group_upload: IconCloudUpload,
  prompts: IconMessage,
  performance: IconGauge,
};

export function ConfigCategoryIcon({
  category,
  className,
}: {
  category: string;
  className?: string;
}) {
  const CategoryIcon = categoryIcons[category] ?? IconAdjustmentsHorizontal;
  return <CategoryIcon aria-hidden="true" stroke={1.6} className={className} />;
}
