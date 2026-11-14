import { useContext } from "react";
import { IconBrain } from "@tabler/icons-react";
import anthropic from "@lobehub/icons-static-svg/icons/anthropic.svg";
import openrouter from "@lobehub/icons-static-svg/icons/openrouter.svg";
import azure from "@lobehub/icons-static-svg/icons/azure.svg";
import siliconflow from "@lobehub/icons-static-svg/icons/siliconcloud.svg";
import dashscope from "@lobehub/icons-static-svg/icons/alibabacloud-color.svg";
import modelscope from "@lobehub/icons-static-svg/icons/modelscope.svg";
import nvidia from "@lobehub/icons-static-svg/icons/nvidia-color.svg";
import longcat from "@lobehub/icons-static-svg/icons/longcat-color.svg";
import ppio from "@lobehub/icons-static-svg/icons/ppio.svg";
import dify from "@lobehub/icons-static-svg/icons/dify-color.svg";
import coze from "@lobehub/icons-static-svg/icons/coze.svg";
import fastgpt from "@lobehub/icons-static-svg/icons/fastgpt-color.svg";
import lm_studio from "@lobehub/icons-static-svg/icons/lmstudio.svg";
import fishaudio from "@lobehub/icons-static-svg/icons/fishaudio.svg";
import ai302 from "@lobehub/icons-static-svg/icons/ai302-color.svg";
import microsoft from "@lobehub/icons-static-svg/icons/microsoft.svg";
import vllm from "@lobehub/icons-static-svg/icons/vllm.svg";
import groq from "@lobehub/icons-static-svg/icons/groq.svg";
import aihubmix from "@lobehub/icons-static-svg/icons/aihubmix-color.svg";
import typesafe from "@lobehub/icons-static-svg/icons/typesafeai.svg";
import vercel from "@lobehub/icons-static-svg/icons/vercel.svg";
import xinference from "@lobehub/icons-static-svg/icons/xinference-color.svg";
import bailian from "@lobehub/icons-static-svg/icons/bailian-color.svg";
import volcengine from "@lobehub/icons-static-svg/icons/volcengine-color.svg";
import huggingface from "@lobehub/icons-static-svg/icons/huggingface.svg";
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
import { ProviderBrandsContext } from "@/entities/config/model/ProviderBrandsContext";

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

// 与宿主常用服务商的图标对齐，模型名称仍使用原有品牌规则。
const providerBrands = new Map(
  Object.entries({
    ...brands,
    anthropic: { src: anthropic, mono: true },
    openrouter: { src: openrouter, mono: true },
    azure: { src: azure, mono: true },
    siliconflow: { src: siliconflow, mono: true },
    dashscope: { src: dashscope, mono: false },
    modelscope: { src: modelscope, mono: true },
    nvidia: { src: nvidia, mono: false },
    longcat: { src: longcat, mono: false },
    ppio: { src: ppio, mono: true },
    dify: { src: dify, mono: false },
    coze: { src: coze, mono: true },
    fastgpt: { src: fastgpt, mono: false },
    lm_studio: { src: lm_studio, mono: true },
    fishaudio: { src: fishaudio, mono: true },
    "302ai": { src: ai302, mono: false },
    microsoft: { src: microsoft, mono: true },
    vllm: { src: vllm, mono: true },
    groq: { src: groq, mono: true },
    aihubmix: { src: aihubmix, mono: false },
    typesafe: { src: typesafe, mono: true },
    vercel: { src: vercel, mono: true },
    xinference: { src: xinference, mono: false },
    bailian: { src: bailian, mono: false },
    volcengine: { src: volcengine, mono: false },
    huggingface: { src: huggingface, mono: true },
    kimi: brands.moonshot,
    "kimi-code": brands.moonshot,
    "minimax-token-plan": brands.minimax,
  }),
);

export function ModelIcon({
  provider,
  model,
  name,
  id,
  type,
  className,
}: {
  provider?: string;
  model?: string;
  name?: string;
  id?: string;
  type?: string;
  className?: string;
}) {
  const providerById = useContext(ProviderBrandsContext);
  const providerKey = provider || (id ? providerById.get(id) : undefined);
  let icon = providerKey ? providerBrands.get(providerKey) : undefined;
  if (!icon) {
    for (const text of [model, name, id]) {
      if (!text) continue;
      const label = text.trim().replace(/_/g, "-");
      const brand = modelBrands.find(([pattern]) => pattern.test(label))?.[1];
      if (brand) {
        icon = brands[brand];
        break;
      }
    }
  }
  if (!icon && type && Object.prototype.hasOwnProperty.call(brands, type))
    icon = brands[type as keyof typeof brands];
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
