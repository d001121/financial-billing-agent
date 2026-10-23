export type JsonObject = Record<string, unknown>;
export type Operation = "CREATE" | "UPDATE" | "NO_CHANGE" | "PENDING_REVIEW";
export interface Issue {
  code: string;
  message: string;
  severity?: string;
  field?: string;
  source_id?: string;
  charge_id?: string;
  expected?: unknown;
  actual?: unknown;
  repairable?: boolean;
  type?: string;
  detail?: string;
}
export interface Asset {
  id: string;
  name: string;
  size?: number;
  media_type?: string;
  url?: string;
  content_url?: string;
  source_url?: string;
  parent_id?: string | null;
  status?: string;
  sample_path?: string;
  path?: string;
  text?: string;
  preview_text?: string;
}
export interface Source {
  source_id: string;
  name: string;
  path?: string;
  size_bytes?: number;
  mime_type?: string;
  parent_source_id?: string | null;
  text?: string;
  preview_text?: string;
  blocks?: JsonObject[];
  status?: string;
}
export interface Evidence {
  source_id?: string;
  asset_id?: string;
  filename?: string;
  page?: number | null;
  anchor?: string;
  quote?: string;
  text?: string;
  field?: string;
  [key: string]: unknown;
}
export interface ConfidenceField {
  score: number | null;
  status: string;
  reasons: string[];
  ambiguity_kind?: "format" | "currency" | "location" | string;
  observations?: {
    raw?: unknown;
    candidates?: unknown;
    reason?: unknown;
    [key: string]: unknown;
  }[];
}
export interface ConfidenceSignal {
  status: "passed" | "unavailable" | "failed";
  reason: string;
}
export interface RecordConfidence {
  charge_id: string;
  record_id?: string;
  origin?: "records" | "charges";
  record?: Charge;
  score: number | null;
  review_score?: number | null;
  review_required?: boolean;
  band: string;
  eligible_for_quick_confirm: boolean;
  components: {
    id: string;
    label: string;
    score: number;
    max_score: number;
    status: string;
    reason: string;
  }[];
  fields: Record<string, ConfidenceField>;
  blockers: Issue[];
  evidence_targets: Evidence[];
  signals?: {
    line_arithmetic?: ConfidenceSignal;
    document_total?: ConfidenceSignal;
  };
  review_route?: "quick_confirm" | "review_suggested" | "blocked";
  fusion?: {
    source_group?: string;
    constraint_group?: string;
    duplicate_bonus?: boolean;
  };
  review_items?: {
    charge_id?: string;
    field: string;
    score?: number | null;
    value?: unknown;
    raw_value?: unknown;
    reason?: string;
  }[];
}
export interface ConfidenceReport {
  revision: number;
  method: string;
  calibrated: boolean;
  score: number | null;
  review_score?: number | null;
  review_required?: boolean;
  policy?: { review_threshold?: number };
  band: string;
  records: RecordConfidence[];
  blockers: Issue[];
  eligible_for_quick_confirm?: boolean;
  summary: string | Record<string, unknown>;
}
export interface PreviewBlock {
  anchor?: string;
  text?: string;
  page?: number;
  sheet?: string;
  row?: number;
  column?: string | number;
  cells?: unknown[];
  table?: unknown;
  cell?: unknown;
  [key: string]: unknown;
}
export interface PreviewTarget extends Evidence {
  located: boolean;
  reason?: string;
  sheet?: string;
  row?: number;
  column?: string | number;
  cell_anchor?: string;
  render_page?: number;
  render_version?: string;
  bbox?: {
    x: number;
    y: number;
    width: number;
    height: number;
    unit: "normalized" | "pixel";
    image_width?: number;
    image_height?: number;
  };
}
export interface OriginalLocation {
  status: "located" | "ambiguous" | "unlocated" | "error";
  reason: string;
  locations: {
    page: number;
    text: string;
    method: string;
    boxes: {
      x: number;
      y: number;
      width: number;
      height: number;
      unit: "normalized";
    }[];
  }[];
  errors?: string[];
}
export interface SourcePreview {
  source_id: string;
  revision: number;
  name: string;
  kind: "pdf" | "image" | "spreadsheet" | "document" | "office" | "text";
  content_url: string;
  blocks: PreviewBlock[];
  target: PreviewTarget;
  original?: OriginalLocation;
  render?: {
    kind: "pdf";
    content_url: string;
    version: string;
    sha256?: string;
    page_count?: number;
  } | null;
  authoritative: boolean;
}
export interface Charge {
  charge_id: string;
  raw_amount?: string | null;
  operation?: Operation;
  document_info: {
    document_type?: string | null;
    reference_no?: string | null;
    document_date?: string | null;
    [key: string]: unknown;
  };
  transaction_party: {
    issuer?: string | null;
    recipient?: string | null;
    [key: string]: unknown;
  };
  charge_details: {
    charge_item?: string | null;
    original_charge_item?: string | null;
    amount?: number | null;
    currency?: string | null;
    payment_term?: string | null;
    quantity?: number | null;
    unit_price?: number | null;
    [key: string]: unknown;
  };
  financial_attributes: {
    accounting_entity?: string | null;
    posting_type?: string | null;
    [key: string]: unknown;
  };
  audit_trail?: {
    ai_reasoning?: string[] | string;
    evidence?: Evidence[];
    operation?: Operation;
    [key: string]: unknown;
  };
  evidence?: Evidence[];
  issues?: Issue[];
  changes?: unknown;
  [key: string]: unknown;
}
export interface Todo {
  content: string;
  status: "pending" | "in_progress" | "completed";
}
export interface Artifact {
  id: string;
  kind: string;
  name: string;
  payload?: unknown;
  url?: string;
  revision?: number;
}
export interface Task {
  review_request?: { id?: string; revision?: number; state?: string; blocking?: boolean;
    question?: string; choices?: string[]; field?: string } | null;
  interrupts?: { id: string; value: unknown }[];
  conversation?: ConversationReply[];
  native_messages?: unknown[];
  id: string;
  title?: string;
  accounting_entity: string | null;
  instructions?: string;
  status: string;
  revision: number;
  control?: string;
  created_at: string;
  updated_at?: string;
  thread_id?: string | null;
  run_id?: string | null;
  asset_ids?: string[];
  assets?: Asset[];
  sources?: Source[];
  records?: Charge[];
  charges?: Charge[];
  record_count?: number;
  issue_count?: number;
  pending_questions?: string[];
  thread_status?: string;
  bill?: {
    id: string;
    material_count: number;
    references: string[];
    parties: string[];
    amounts: { amount: number | null; currency: string | null }[];
    attention: Issue[];
    materials: {
      source_id: string;
      name: string;
      parent_source_id?: string | null;
      status?: string;
      format?: string;
    }[];
  };
  issues?: Issue[];
  todos?: Todo[];
  intake_issues?: Issue[];
  intake_progress?: { stage: string; name?: string };
  intake_preview?: {
    source_id: string;
    name: string;
    rows: {
      description: string;
      raw_amount?: string;
      amount?: string;
      currency?: string | null;
      page?: number;
    }[];
  }[];
  summary?: string;
  run_status?: string;
  feedback?: {
    revision: number;
    state: string;
    model_seen?: boolean;
    reason?: string;
  } | null;
  exportable?: boolean;
  export_ready?: boolean;
  usage?: JsonObject;
  capability?: {
    version?: string | number;
    config?: {
      runtime?: {
        model_calls?: number;
        tool_calls?: number;
        active_seconds?: number;
      };
    };
  };
  validation?: JsonObject;
  totals?: unknown[];
  coverage?: unknown;
  approval?: { decision?: string; binding?: { revision?: number } } | null;
  auto_review?: {
    decision?: string;
    mode?: string;
    binding?: { revision?: number };
  } | null;
  review_confirmation?: {
    decision?: string;
    revision?: number;
    at?: string;
    reason?: string;
  } | null;
  confidence_interrupt?: { kind: string; revision: number } | null;
  error?: string | null;
  artifacts?: Artifact[];
}
export interface ConversationReply {
  id: string;
  text: string;
  question: string;
  interrupt_id: string;
  kind?: string;
  tool_call_id?: string | null;
  anchor_message_id?: string | null;
  revision: number;
  state: string;
  at: string;
}
export interface TraceOverview {
  tasks: (Task & { event_counts: Record<string, number> })[];
  sample_size: number;
  limit: number;
  human: {
    revised_tasks: number;
    revision_ratio: number | null;
    confirmation_tasks: number;
    waiting_input_tasks: number;
    definition: string;
  };
  quality: {
    accuracy: number | null;
    false_positive_rate: number | null;
    false_negative_rate: number | null;
    labeled_samples: number;
    status: string;
    reason: string;
  };
}
export interface TaskTrace {
  task_id: string;
  revision: number;
  usage: JsonObject;
  events: {
    id?: string;
    event: string;
    at?: string;
    tool?: string;
    call_id?: string;
    revision?: number;
    status?: string;
    elapsed_seconds?: number;
    message?: string;
    reason?: string;
  }[];
  events_truncated: boolean;
  event_counts: Record<string, number>;
  call_path: {
    call_id?: string;
    tool?: string;
    namespace: string[];
    parent_task_id?: string;
    agent?: string;
  }[];
  state_error?: string;
  path_scope: string;
}
export interface Health {
  status?: string;
  services?: Record<
    string,
    | { status?: string; available?: boolean; message?: string }
    | string
    | boolean
  >;
  version?: string;
}
export interface NewTask {
  title: string;
  accounting_entity: string | null;
  asset_ids: string[];
  existing_records?: JsonObject[];
  history_mode?: "automatic" | "provided";
  instructions: string;
}
export interface Revision {
  expected_revision: number;
  reason: string;
  operations: {
    op: "set" | "delete" | "split";
    charge_id?: string;
    field?: string;
    value?: unknown;
  }[];
  accounting_entity?: string;
}
export interface ConfigDocument {
  kind: string;
  version: number | string;
  config: unknown;
  [key: string]: unknown;
}
export interface ImprovementCandidate {
  id: string;
  candidate_id?: string;
  kind: string;
  status: string;
  source?: { task_id?: string; revision?: number; [key: string]: unknown };
  scope?: JsonObject;
  proposed_by?: string;
  before?: JsonObject;
  after?: JsonObject;
  base_version?: string;
  revision?: number;
  created_at?: string;
  comparison?: {
    passed?: boolean;
    baseline_passes?: number;
    candidate_passes?: number;
    total_cases?: number;
    synthetic?: boolean;
    engine?: string;
    issues?: unknown[];
    report?: unknown;
    [key: string]: unknown;
  };
}
export interface ImprovementRegistry {
  active_version?: string;
  versions?: Record<string, unknown> | unknown[];
  rollbacks?: unknown[];
  [key: string]: unknown;
}
export interface ExperienceCard {
  id: string;
  revision: number;
  status: "draft" | "active" | "paused";
  title: string;
  problem: string;
  applicability: string;
  recommendation: string;
  exceptions: string;
  keywords: string[];
  accounting_entity: string | null;
  created_at?: string;
  source: {
    task_id: string;
    revision: number;
    title?: string;
    artifact_digest?: string;
  };
  source_refs: { source_id: string; quote?: string; anchor?: string }[];
  summary_id?: string;
}
export interface ExperienceReference {
  id: string;
  experience_id: string;
  experience_revision: number;
  task_id: string;
  task_title?: string;
  task_revision: number;
  query: string;
  at?: string;
  outcome: "retrieved";
}
export const operationLabels: Record<Operation, string> = {
  CREATE: "新增",
  UPDATE: "更新",
  NO_CHANGE: "无变更",
  PENDING_REVIEW: "待复核",
};
export const taskStatusLabels: Record<string, string> = {
  pending: "等待处理",
  queued: "排队中",
  running: "处理中",
  processing: "处理中",
  completed: "已完成",
  completed_with_gaps: "已提取 · 信息待完善",
  incomplete: "处理未完成",
  review_deferred: "暂缓复核",
  failed: "处理失败",
  error: "处理失败",
  waiting_input: "待补充",
  awaiting_input: "待补充",
  waiting_review: "待复核",
  awaiting_review: "待复核",
  ready_for_review: "待复核",
  approved: "已批准",
  needs_input: "待补充",
  needs_review: "待复核",
  interrupted: "待人工介入",
  paused: "已暂停",
  pausing: "暂停中",
  cancelled: "已取消",
  recovery_required: "需要恢复",
  budget_exhausted: "处理额度已用尽",
  draft: "草稿",
  succeeded: "已完成",
};
export function chargeOperation(record: Charge): Operation | undefined {
  return record.operation || record.audit_trail?.operation;
}
export function formatDate(value?: string): string {
  return value
    ? new Date(value).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
}
export function formatSize(size?: number): string {
  return size == null
    ? "原始材料"
    : size >= 1048576
      ? `${(size / 1048576).toFixed(1)} MB`
      : `${Math.max(1, Math.round(size / 1024))} KB`;
}
