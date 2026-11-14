import { render } from "@testing-library/react";
import { expect, it } from "vitest";
import { PlatformIcon } from "@/entities/group/ui/PlatformIcon";

it("沿用宿主的平台标识，未知实例不误标成 QQ", () => {
  const view = render(<PlatformIcon platform="aiocqhttp" />);
  expect(view.container.querySelector("img")?.src).toContain("onebot.png");
  view.rerender(<PlatformIcon platform="qq_official_webhook" />);
  expect(view.container.querySelector("img")?.src).toContain("qq.png");
  view.rerender(<PlatformIcon platform="Satori" />);
  expect(view.container.querySelector("img")?.src).toContain("satori.png");
  view.rerender(<PlatformIcon platform="my-bot-01" />);
  expect(view.container.querySelector("img")).toBeNull();
  expect(view.container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
});
