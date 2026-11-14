import { useContext } from "react";
import { IconMessages } from "@tabler/icons-react";
import { PlatformTypesContext } from "@/entities/group/model/PlatformTypesContext";
import onebot from "@/shared/assets/platforms/onebot.png";
import qq from "@/shared/assets/platforms/qq.png";
import satori from "@/shared/assets/platforms/satori.png";
import telegram from "@/shared/assets/platforms/telegram.svg";
import discord from "@/shared/assets/platforms/discord.svg";
import { cn } from "@/shared/lib/cn";

const platformIcons = new Map([
  ["aiocqhttp", onebot],
  ["onebot", onebot],
  ["qq_official", qq],
  ["qq_official_webhook", qq],
  ["satori", satori],
  ["telegram", telegram],
  ["discord", discord],
  ["discord_bot", discord],
]);

export function PlatformIcon({ platform, className }: { platform?: string; className?: string }) {
  const types = useContext(PlatformTypesContext);
  // 按实例 ID 精确查找。历史记录直接存适配器类型时，仍可用类型匹配。
  const type = platform ? (types.get(platform) ?? platform) : "";
  const src = platformIcons.get(type.trim().toLowerCase());
  if (!src)
    return (
      <IconMessages
        aria-hidden="true"
        className={cn("size-5 shrink-0 text-muted-foreground", className)}
      />
    );
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex size-6 shrink-0 items-center justify-center rounded-md bg-white p-0.5",
        className,
      )}
    >
      <img src={src} alt="" className="size-full object-contain" />
    </span>
  );
}
