import { z } from "zod";

// 历史评价允许保留额外字段；无法识别的结构由详情页显示原始数据。
export const batchQualityReviewSchema = z.looseObject({
  title: z.string().optional(),
  subtitle: z.string().optional(),
  summary: z.string().optional(),
  dimensions: z
    .array(
      z.looseObject({
        name: z.string().optional(),
        percentage: z.number().finite().optional(),
        comment: z.string().optional(),
      }),
    )
    .optional(),
});
