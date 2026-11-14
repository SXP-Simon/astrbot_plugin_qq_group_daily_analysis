import { IconBrain } from "@tabler/icons-react";
import openai from "@lobehub/icons-static-svg/icons/openai.svg";
import claude from "@lobehub/icons-static-svg/icons/claude-color.svg";
import deepseek from "@lobehub/icons-static-svg/icons/deepseek-color.svg";
import gemini from "@lobehub/icons-static-svg/icons/gemini-color.svg";
import qwen from "@lobehub/icons-static-svg/icons/qwen-color.svg";
import ollama from "@lobehub/icons-static-svg/icons/ollama.svg";
import xai from "@lobehub/icons-static-svg/icons/xai.svg";
import kimi from "@lobehub/icons-static-svg/icons/kimi.svg";
import glm from "@lobehub/icons-static-svg/icons/zhipu.svg";
import minimax from "@lobehub/icons-static-svg/icons/minimax.svg";
import doubao from "@lobehub/icons-static-svg/icons/doubao-color.svg";
import mistral from "@lobehub/icons-static-svg/icons/mistral-color.svg";
import { cn } from "@/shared/lib/cn";

const brands = {
  openai: { src: openai, mono: true },
  anthropic: { src: claude, mono: false },
  deepseek: { src: deepseek, mono: false },
  google: { src: gemini, mono: false },
  qwen: { src: qwen, mono: false },
  ollama: { src: ollama, mono: true },
  xai: { src: xai, mono: true },
  moonshot: { src: kimi, mono: true },
  zhipu: { src: glm, mono: true },
  minimax: { src: minimax, mono: true },
  doubao: { src: doubao, mono: false },
  mistral: { src: mistral, mono: false },
};

const modelBrands: [RegExp, keyof typeof brands][] = [
  [/\bdeepseek\b/i, "deepseek"],
  [/\bclaude\b/i, "anthropic"],
  [/\bgemini\b/i, "google"],
  [/\bqwen(?:\d|\b)/i, "qwen"],
  [/\b(?:gpt|chatgpt|o[134])\b|^openai$/i, "openai"],
  [/\bgrok\b/i, "xai"],
  [/\bkimi\b/i, "moonshot"],
  [/\bglm\b/i, "zhipu"],
  [/\bminimax\b/i, "minimax"],
  [/\bdoubao\b/i, "doubao"],
  [/\b(?:mistral|mixtral)\b/i, "mistral"],
  [/\bollama\b/i, "ollama"],
];

export function ModelIcon({
  model,
  name,
  id,
  type,
  className,
}: {
  model?: string;
  name?: string;
  id?: string;
  type?: string;
  className?: string;
}) {
  // 优先识别实际模型，其次识别展示名称和编号；兼容协议本身不能证明模型品牌。
  let brand: keyof typeof brands | undefined;
  for (const text of [model, name, id]) {
    if (!text) continue;
    const label = text.trim().replace(/_/g, "-");
    brand = modelBrands.find(([pattern]) => pattern.test(label))?.[1];
    if (brand) break;
  }
  if (!brand && type && Object.prototype.hasOwnProperty.call(brands, type))
    brand = type as keyof typeof brands;
  const icon = brand ? brands[brand] : undefined;
  if (!icon)
    return (
      <IconBrain
        aria-hidden="true"
        className={cn("size-5 shrink-0 text-muted-foreground", className)}
      />
    );
  return (
    <img
      src={icon.src}
      alt=""
      aria-hidden="true"
      className={cn("size-5 shrink-0 object-contain", icon.mono && "dark:invert", className)}
    />
  );
}
