import type { ReactNode } from "react";
import { Button, Popover, Typography } from "antd";

/** 宿主插件页不允许弹窗，提供可手动复制的外部地址。 */
export function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Popover
      trigger="click"
      title={children}
      content={
        <div style={{ maxWidth: 420 }}>
          <Typography.Paragraph>复制地址后，在浏览器新标签页打开：</Typography.Paragraph>
          <Typography.Paragraph copyable style={{ overflowWrap: "anywhere", userSelect: "text" }}>
            {href}
          </Typography.Paragraph>
        </div>
      }
    >
      <Button type="link" size="small" style={{ paddingInline: 0 }}>
        {children}
      </Button>
    </Popover>
  );
}
