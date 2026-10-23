import type { Issue, Task } from "../types/contracts";

export type TaskFilter =
  | "all"
  | "review"
  | "active"
  | "completed"
  | "attention";
export type TaskCategory = Exclude<TaskFilter, "all">;

const reviewStatuses = new Set([
  "waiting_input",
  "awaiting_input",
  "needs_input",
  "interrupted",
  "waiting_review",
  "awaiting_review",
  "needs_review",
  "ready_for_review",
  "review_deferred",
]);
const activeStatuses = new Set([
  "pending",
  "queued",
  "starting",
  "running",
  "processing",
  "pausing",
]);
const completedStatuses = new Set(["approved", "completed", "succeeded", "completed_with_gaps"]);

/** Presentation only: framework run success does not approve a business task. */
export function taskCategory(task: Task): TaskCategory {
  if (
    task.approval?.decision === "approve" &&
    task.approval.binding?.revision === task.revision
  )
    return "completed";
  if (reviewStatuses.has(task.status)) return "review";
  if (activeStatuses.has(task.status)) return "active";
  if (completedStatuses.has(task.status)) return "completed";
  return "attention";
}

export function taskTitle(task: Task): string {
  return task.title?.trim() || task.bill?.references[0] || "未命名账单";
}

export function billAttention(task: Task): string {
  if (
    ["waiting_input", "awaiting_input", "needs_input", "interrupted"].includes(
      task.status,
    )
  )
    return task.pending_questions?.[0] || "请补充智能体请求的信息";
  if (task.status === "approved" ||
      (task.approval?.decision === "approve" && task.approval.binding?.revision === task.revision))
    return "当前版本已批准，可查看或导出账单";
  if (taskIsProcessing(task)) return "正在处理材料，完成后可核对账单";
  if (taskCategory(task) === "review") return "仅需核对低置信度字段，可直接查看原文并修改";
  if (task.status === 'completed_with_gaps') return "提取结果已保存，可查看原文及完善信息";
  if (taskCategory(task) === "completed") return "已完成核验，可查看、修改或导出结果";
  return taskNextAction(task);
}

export function taskIsProcessing(task: Task): boolean {
  // Native runs include chat and may retain an older pending indicator in
  // list snapshots. Material progress follows the same business category as
  // the status badge; a run indicator must not reopen a settled bill.
  return taskCategory(task) === "active";
}

export function issueMessage(issue: Issue): string {
  const labels: Record<string, string> = {
    ambiguous_amount: "金额格式有多种解释，请对照原件确认。",
    ambiguous_currency: "币种符号含义不明确，请补充具体币种。",
  };
  return (
    issue.message ||
    labels[issue.type || ""] ||
    issue.detail ||
    issue.code ||
    "该项信息需要核对，请查看相关费用与原件。"
  );
}

export function taskNextAction(task: Task): string {
  if (["waiting_input", "awaiting_input", "needs_input"].includes(task.status))
    return "补充信息";
  if (task.status === "interrupted") return "处理人工请求";
  if (task.status === "ready_for_review") return "核对并确认";
  if (taskCategory(task) === "review") return "处理复核项";
  if (taskCategory(task) === "active") return "查看进度";
  if (taskCategory(task) === "completed") return "查看结果";
  if (task.status === "budget_exhausted") return "查看未完成范围";
  if (task.status === "paused") return "查看暂停任务";
  if (task.status === "recovery_required") return "检查恢复条件";
  if (["failed", "error"].includes(task.status)) return "查看失败原因";
  return "查看详情";
}

export function recordCount(task: Task): number {
  return task.record_count ?? task.records?.length ?? 0;
}

export function taskTime(task: Task): string {
  return task.updated_at || task.created_at;
}
