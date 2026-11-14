import { IconMessages } from "@tabler/icons-react";
import onebot from "@/shared/assets/platforms/onebot.png";
import qq from "@/shared/assets/platforms/qq.png";
import satori from "@/shared/assets/platforms/satori.png";
import telegram from "@/shared/assets/platforms/telegram.svg";
import discord from "@/shared/assets/platforms/discord.svg";
import { cn } from "@/shared/lib/cn";

// 与 AstrBot 的平台类型映射一致；实例 ID 不猜测为某个平台。
const platformIcons: Record<string, string> = {
  aiocqhttp: onebot,
  qq_official: qq,
  qq_official_webhook: qq,
  satori,
  telegram,
  discord,
};

export function PlatformIcon({ platform, className }: { platform?: string; className?: string }) {
  const src = platformIcons[platform?.toLowerCase() ?? ""];
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
