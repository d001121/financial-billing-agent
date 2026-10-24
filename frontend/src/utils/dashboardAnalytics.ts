import type { Task } from "../types/contracts";
import { taskCategory, type TaskCategory } from "./taskPresentation.ts";

export const dashboardStates = [
  { id: "completed", label: "完成", color: "#365d99" },
  { id: "review", label: "待复核", color: "#d4a13b" },
  { id: "active", label: "处理中", color: "#5b8b80" },
  { id: "attention", label: "暂停 / 异常", color: "#c9797b" },
] as const;

export function localDay(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export interface DashboardDateRange { start: string; end: string }
function parseLocalDay(value: string): Date {
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!parts) throw new RangeError("Invalid dashboard date");
  const date = new Date(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3]));
  if (localDay(date) !== value) throw new RangeError("Invalid dashboard date");
  return date;
}
/** Creation cohorts use current business status, never historical completion time. Custom end is inclusive. */
export function dashboardAnalytics(tasks: Task[], days: number | null | DashboardDateRange, now: Date) {
  const custom = typeof days === "object" && days !== null ? days : null;
  const end = custom ? parseLocalDay(custom.end) : new Date(now.getFullYear(), now.getMonth(), now.getDate());
  end.setDate(end.getDate() + 1);
  const dated = tasks.map(task => ({ task, date: new Date(task.created_at) }))
    .filter(row => Number.isFinite(row.date.getTime()));
  const first = custom ? parseLocalDay(custom.start).getTime() : days === null
    ? Math.min(new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime(), ...dated.map(row => row.date.getTime()))
    : new Date(now.getFullYear(), now.getMonth(), now.getDate() - (days as number) + 1).getTime();
  const start = new Date(first);
  start.setHours(0, 0, 0, 0);
  if (start >= end) throw new RangeError("Dashboard start date must not follow end date");
  const included = dated.filter(row => row.date >= start && row.date < end);
  const counts: Record<TaskCategory, number> = { completed: 0, review: 0, active: 0, attention: 0 };
  const daily: { date: string; label: string; total: number; counts: Record<TaskCategory, number> }[] = [];
  for (const date = new Date(start); date < end; date.setDate(date.getDate() + 1)) {
    daily.push({ date: localDay(date), label: `${date.getMonth() + 1}/${date.getDate()}`, total: 0,
      counts: { completed: 0, review: 0, active: 0, attention: 0 } });
  }
  const byDay = new Map(daily.map(day => [day.date, day]));
  const entities = new Map<string, number>();
  const heat = Array.from({ length: 7 }, () => Array<number>(24).fill(0));
  for (const { task, date } of included) {
    const state = taskCategory(task);
    counts[state]++;
    const day = byDay.get(localDay(date))!;
    day.total++; day.counts[state]++;
    const entity = task.accounting_entity?.trim() || "主体未提供";
    entities.set(entity, (entities.get(entity) || 0) + 1);
    heat[(date.getDay() + 6) % 7]![date.getHours()]!++;
  }
  return {
    tasks: included.map(row => row.task), counts, daily,
    entities: [...entities].sort((a, b) => b[1] - a[1]),
    heat: heat.flatMap((row, weekday) => row.map((count, hour) => [hour, weekday, count])),
    start: localDay(start), end: localDay(new Date(end.getTime() - 1)),
    undated: tasks.length - dated.length,
  };
}
