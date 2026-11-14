import { render } from "@testing-library/react";
import { expect, it } from "vitest";
import { PlatformIcon } from "@/entities/group/ui/PlatformIcon";
import { PlatformTypesContext } from "@/entities/group/model/PlatformTypesContext";

it("按实例元数据获取适配器图标，元数据优先于同名类型", () => {
  const { container } = render(
    <PlatformTypesContext.Provider
      value={
        new Map([
          ["aoi", "aiocqhttp"],
          ["aiocqhttp", "telegram"],
          ["任意东西", "qq_official"],
        ])
      }
    >
      <PlatformIcon platform="aoi" />
      <PlatformIcon platform="aiocqhttp" />
      <PlatformIcon platform="任意东西" />
    </PlatformTypesContext.Provider>,
  );
  const [onebot, telegram, qq] = container.querySelectorAll("img");
  expect(onebot.src).toContain("onebot.png");
  expect(telegram.src).toContain("telegram.svg");
  expect(qq.src).toContain("qq.png");
});

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
