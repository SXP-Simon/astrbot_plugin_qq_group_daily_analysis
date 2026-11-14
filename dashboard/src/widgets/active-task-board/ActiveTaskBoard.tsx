import { useId, useRef } from "react";
import { IconArrowRight, IconPlus } from "@tabler/icons-react";
import { PlatformIcon } from "@/entities/group/ui/PlatformIcon";
import type { ActiveTask } from "@/entities/task/model/types";
import { TaskStageBadge } from "@/entities/task/ui/TaskStageBadge";
import { CancelTaskButton } from "@/features/cancel-task/ui/CancelTaskButton";
import { Button } from "@/shared/ui/button";
import { TriggerTypeTag } from "@/shared/ui/TriggerTypeTag";

interface ActiveTaskBoardProps {
  tasks: ActiveTask[];
  onCancelTask: (taskId: string) => Promise<boolean | void> | boolean | void;
  onViewTrace: (traceId: string) => void;
  onOpenTrigger: () => void;
}

export function ActiveTaskBoard({
  tasks,
  onCancelTask,
  onViewTrace,
  onOpenTrigger,
}: ActiveTaskBoardProps) {
  const headingId = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  return (
    <section aria-labelledby={headingId} className="min-w-0">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2
          id={headingId}
          ref={heading}
          tabIndex={-1}
          className="m-0 rounded-md text-lg font-medium focus-visible:outline-2 focus-visible:outline-ring"
        >
          正在执行中的分析任务{" "}
          <span className="ml-2 text-sm text-muted-foreground">{tasks.length} 运行中</span>
        </h2>
        <Button size="sm" variant="outline" onClick={onOpenTrigger}>
          <IconPlus aria-hidden="true" />
          发起分析
        </Button>
      </div>
      {tasks.length === 0 ? (
        <p className="m-0 py-8 text-sm text-muted-foreground">暂无正在执行的后台分析任务</p>
      ) : (
        <ul className="m-0 list-none p-0">
          {tasks.map((task) => (
            <li
              key={task.task_id}
              className="grid min-w-0 gap-3 border-0 border-b border-solid border-border py-4 last:border-b-0 lg:grid-cols-[minmax(0,1fr)_minmax(160px,0.65fr)_auto] lg:items-center"
            >
              <div className="min-w-0 space-y-1">
                <h3 className="m-0 break-words text-base font-medium">
                  {task.group_name || "未命名群聊"}
                </h3>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  <span className="inline-flex min-w-0 items-center gap-1.5 font-mono">
                    <PlatformIcon platform={task.platform} className="size-4" />
                    <span className="min-w-0 break-all">
                      {task.platform && !["auto", "default"].includes(task.platform) ? (
                        task.platform
                      ) : (
                        <span className="font-sans">平台未记录</span>
                      )}{" "}
                      · {task.group_id}
                    </span>
                  </span>
                  <TriggerTypeTag triggerType={task.trigger_type} />
                </div>
                <p className="m-0 break-all font-mono text-xs text-muted-foreground">
                  {task.task_id}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 lg:flex-col lg:items-start">
                <TaskStageBadge stage={task.current_stage} />
                <span className="text-xs text-muted-foreground">
                  已运行{" "}
                  <span className="font-mono tabular-nums">
                    {Number.isFinite(task.duration_s) && task.duration_s >= 0
                      ? `${Math.round(task.duration_s * 10) / 10} 秒`
                      : "未记录"}
                  </span>
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-1">
                <Button size="sm" variant="outline" onClick={() => onViewTrace(task.task_id)}>
                  查看详情
                  <IconArrowRight aria-hidden="true" />
                </Button>
                <CancelTaskButton
                  taskId={task.task_id}
                  taskLabel={task.group_name || task.group_id}
                  onCancel={onCancelTask}
                  onRemovedFocus={() => heading.current?.focus()}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
