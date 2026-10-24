// Development-only entry: render the real app against synthetic, read-only responses.
// Vite's production entry remains index.html; no demo fixtures enter the app bundle.
const id = "ocean-demo";
const at = "2026-10-24T10:00:00+08:00";
const records = [
  { charge_id: "demo-doc", name: "文件费", original: "Documentation Fee", amount: 65 },
  { charge_id: "demo-release", name: "电放费", original: "Telex Release", amount: 35 },
].map(row => ({
  charge_id: row.charge_id, operation: "PENDING_REVIEW",
  document_info: { document_type: "Invoice", reference_no: "INV-DEMO-1024", document_date: "2026-10-24" },
  transaction_party: { issuer: "Demo Shipping Ltd", recipient: "Demo Trading Ltd" },
  charge_details: { charge_item: row.name, original_charge_item: row.original, amount: row.amount, currency: "USD", payment_term: null },
  financial_attributes: { accounting_entity: "Demo Trading Ltd", posting_type: "AP" },
  evidence: [{ source_id: "demo-source", filename: "demo-invoice.txt", anchor: row.charge_id, quote: `${row.original}  USD ${row.amount}.00` }],
  audit_trail: { ai_reasoning: ["本条仅为界面合成样例，未调用任何模型或财务服务。"] },
}));
const task = {
  id, title: "合成航运账单", accounting_entity: "Demo Trading Ltd", status: "completed_with_gaps", revision: 1,
  created_at: at, updated_at: at, run_status: "success", thread_id: "00000000-0000-4000-8000-000000000024",
  records, asset_ids: ["demo-source"], issues: [], record_count: 2, issue_count: 0, export_ready: false,
  todos: [{ content: "核对第二笔费用是否属于本次账单", status: "pending" }],
  sources: [{ source_id: "demo-source", name: "demo-invoice.txt", mime_type: "text/plain", size_bytes: 128, status: "completed", text: "Documentation Fee  USD 65.00\nTelex Release  USD 35.00" }],
  native_messages: [
    { id: "demo-ai-1", type: "ai", content: "已整理两笔费用，并关联了原文。付款方式在材料中未提供，保持留空。" },
    { id: "chat-user-demo-reply-1", type: "human", content: "文件费的金额和币种没有问题。" },
    { id: "demo-ai-2", type: "ai", content: "好的。你可以继续核对电放费，或随时告诉我需要修改的字段。" },
  ],
  conversation: [{ id: "demo-reply-1", kind: "chat", text: "文件费的金额和币种没有问题。", question: "", interrupt_id: "", revision: 1, state: "completed", at, anchor_message_id: "demo-ai-1", response_message_id: "demo-ai-2" }],
  bill: { id, material_count: 1, references: ["INV-DEMO-1024"], parties: ["Demo Shipping Ltd", "Demo Trading Ltd"], amounts: [{ amount: 100, currency: "USD" }], attention: [], materials: [{ source_id: "demo-source", name: "demo-invoice.txt", status: "completed" }] },
};
const tasks = [task, { ...task, id: "ocean-demo-finished", title: "合成历史账单", status: "approved", thread_id: null, created_at: "2026-10-23T09:00:00+08:00" }];
const confidence = {
  revision: 1, method: "offline-visual-fixture", calibrated: false, score: 80, band: "medium", blockers: [],
  summary: "离线合成界面数据，不代表实际提取或准确率。",
  records: records.map(record => ({ charge_id: record.charge_id, record, origin: "records", score: 80, band: "medium", eligible_for_quick_confirm: false, components: [], blockers: [], evidence_targets: record.evidence,
    fields: Object.fromEntries(["posting_type", "reference_no", "charge_item", "amount", "currency", "payment_term"].map(field => [field, { score: field === "payment_term" ? 0 : 90, status: field === "payment_term" ? "missing" : "supported", reasons: [] }])) })),
};
const state = { values: { messages: task.native_messages, todos: task.todos }, next: [], tasks: [], metadata: {}, created_at: at, checkpoint: { checkpoint_id: "demo-checkpoint", checkpoint_ns: "" } };
const originalFetch = window.fetch.bind(window);
window.fetch = async (input, init) => {
  const url = new URL(input instanceof Request ? input.url : String(input), window.location.href);
  const path = url.pathname;
  const method = init?.method || (input instanceof Request ? input.method : "GET");
  const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
  if (path.startsWith("/threads") || path.startsWith("/assistants") || path.startsWith("/runs")) {
    if (path.endsWith("/state")) return json(state);
    if (path.endsWith("/history")) return json([state]);
    if (path.endsWith("/runs")) return json([]);
    return json({ thread_id: task.thread_id, status: "idle", ...state });
  }
  if (!path.startsWith("/api/")) return originalFetch(input, init);
  if (method !== "GET") return json({ detail: "离线界面预览：不执行提交、回复、修订、审批或删除。" }, 405);
  if (path === "/api/health") return json({ status: "ok", version: "offline-visual-fixture" });
  if (path === "/api/bills" || path === "/api/tasks") return json(tasks);
  if (path === "/api/assets" || path === "/api/samples") return json([]);
  if (path.endsWith("/confidence")) return json(confidence);
  if (path.includes("/sources/") && path.endsWith("/preview")) return json({ revision: 1, source_id: "demo-source", name: "demo-invoice.txt", kind: "text", content_url: "", authoritative: true, blocks: [{ anchor: "demo-doc", text: task.sources[0]!.text, kind: "text" }], target: { located: true, anchor: "demo-doc", quote: "Documentation Fee", field: "amount" } });
  if (path.startsWith("/api/tasks/")) return json({ ...task, id: path.split("/")[3] });
  if (path === "/api/traces") return json({ tasks: [], sample_size: 0, limit: 50, human: { revised_tasks: 0, revision_ratio: null, confirmation_tasks: 0, waiting_input_tasks: 0, definition: "离线界面样例" }, quality: { accuracy: null, false_positive_rate: null, false_negative_rate: null, labeled_samples: 0, status: "not_evaluated", reason: "离线界面样例" } });
  if (path.includes("/experiences")) return json({ experiences: [], references: [] });
  if (path.includes("/improvements")) return json({ candidates: [], datasets: [], versions: [] });
  return json({ detail: "离线预览不连接此管理数据源。" }, 503);
};
if (!window.location.hash) window.location.hash = "/tasks/ocean-demo";
await import("../../src/main");
const label = document.createElement("div");
label.textContent = "离线界面样例 · 合成数据 · 不连接后端或模型";
label.style.cssText = "position:fixed;bottom:4px;left:12px;z-index:90;font:10px sans-serif;color:#496a64;background:#edf3f1;padding:3px 6px;border-radius:4px;pointer-events:none";
document.body.append(label);
