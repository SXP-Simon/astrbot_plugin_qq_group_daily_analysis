import { render } from "@testing-library/react";
import { expect, it } from "vitest";
import { ModelIcon } from "@/entities/config/ui/ModelIcon";
import { ProviderBrandsContext } from "@/entities/config/model/ProviderBrandsContext";

it("宿主服务商品牌优先于模型名，运行记录可通过 ID 读取品牌", () => {
  const view = render(
    <ProviderBrandsContext.Provider value={new Map([["custom-id", "ollama"]])}>
      <ModelIcon id="custom-id" model="qwen3" />
    </ProviderBrandsContext.Provider>,
  );
  expect(view.container.querySelector("img")?.src).toContain("ollama.svg");
  view.rerender(<ModelIcon provider="openrouter" model="claude-sonnet" />);
  expect(view.container.querySelector("img")?.src).toContain("openrouter.svg");
  view.rerender(<ModelIcon provider="anthropic" model="claude-sonnet" />);
  expect(view.container.querySelector("img")?.src).toContain("anthropic.svg");
  view.rerender(<ModelIcon provider="openai_compatible" model="deepseek-chat" />);
  expect(view.container.querySelector("img")?.src).toContain("deepseek-color.svg");
});

it("优先展示真实模型品牌，不把兼容协议或中转服务当成模型品牌", () => {
  const view = render(<ModelIcon model="deepseek-chat" name="OpenAI 中转" type="openai" />);
  expect(view.container.querySelector("img")?.src).toContain("deepseek-color.svg");
  view.rerender(<ModelIcon name="Claude 3.5 Sonnet" type="openai_compatible" />);
  expect(view.container.querySelector("img")?.src).toContain("claude-color.svg");
  view.rerender(<ModelIcon name="Ollama (Local Qwen2.5-7B)" type="openai_compatible" />);
  expect(view.container.querySelector("img")?.src).toContain("qwen-color.svg");
  view.rerender(<ModelIcon name="自定义模型" type="openai_compatible" />);
  expect(view.container.querySelector("img")).toBeNull();
  expect(view.container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
});

it("明确的提供商可作为回退，单色图标适配深色主题且不改变可访问名称", () => {
  const view = render(<ModelIcon name="我的主模型" type="openai" />);
  const icon = view.container.querySelector("img");
  expect(icon?.src).toContain("openai.svg");
  expect(icon).toHaveClass("dark:invert");
  expect(icon).toHaveAttribute("alt", "");
  view.rerender(<ModelIcon model="gemini-2.5-pro" />);
  expect(view.container.querySelector("img")).not.toHaveClass("dark:invert");
});

it("运行记录只有模型 ID 时仍可识别品牌，兼容协议 ID 使用通用图标", () => {
  const view = render(<ModelIcon id="openai" />);
  expect(view.container.querySelector("img")?.src).toContain("openai.svg");
  view.rerender(<ModelIcon id="ollama_local" />);
  expect(view.container.querySelector("img")?.src).toContain("ollama.svg");
  view.rerender(<ModelIcon id="openai_compatible" />);
  expect(view.container.querySelector("img")).toBeNull();
});
