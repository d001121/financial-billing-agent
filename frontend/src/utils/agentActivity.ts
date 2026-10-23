import { AIMessage, ToolMessage, type BaseMessage } from "@langchain/core/messages";
import type { AssembledToolCall } from "@langchain/vue";
import type { ConversationReply } from '../types/contracts';

export type ActivityEntry =
  | { id: string; kind: "message"; text: string; role: 'assistant' | 'user'; delivery?: string }
  | { id: string; kind: "tool"; tool: AssembledToolCall };

// The SDK owns assembly and status. This is only a display order over its projections.
export function activityEntries(messages: BaseMessage[], tools: AssembledToolCall[], replies: ConversationReply[] = []): ActivityEntry[] {
  const byId = new Map(tools.map((tool) => [tool.id, tool]));
  const used = new Set<string>();
  const entries: ActivityEntry[] = [];
  const shownReplies = new Set<string>();
  const shownQuestions = new Set<string>();
  const addReply = (reply: ConversationReply) => {
    if (shownReplies.has(reply.id)) return;
    if (reply.tool_call_id && reply.question && !shownQuestions.has(reply.tool_call_id)) {
      entries.push({id:`question:${reply.id}`,kind:'message',text:reply.question,role:'assistant'});
      shownQuestions.add(reply.tool_call_id);
    }
    entries.push({id: `reply:${reply.id}`, kind:'message', text:reply.text, role:'user', delivery:reply.state});
    shownReplies.add(reply.id);
  };
  for (const [index, message] of messages.entries()) {
    // Historical native ask_user replies are ToolMessages, not HumanMessages.
    // Initial/internal user task snapshots must never be presented as human chat.
    if (ToolMessage.isInstance(message) && message.name === 'ask_user' &&
        !replies.some(r => r.tool_call_id === message.tool_call_id) && message.text.trim()) {
      entries.push({id:`answer:${message.id || index}`, kind:'message', text:message.text, role:'user'});
    }
    if (!AIMessage.isInstance(message)) {
      replies.filter(r => r.kind === 'chat' && message.id === `chat-user-${r.id}`).forEach(addReply);
      continue;
    }
    if (message.text.trim()) entries.push({ id: `message:${message.id || index}`, kind: "message", text: message.text, role:'assistant' });
    for (const call of message.tool_calls || []) {
      const question = (call.args as Record<string, unknown> | null)?.question;
      if (call.name === 'ask_user' && typeof question === 'string') {
        entries.push({id:`question:${call.id}`,kind:'message',text:question,role:'assistant'});
        shownQuestions.add(call.id || '');
      }
      const tool = byId.get(call.id || "");
      if (tool && !used.has(tool.id)) {
        entries.push({ id: `tool:${tool.id}`, kind: "tool", tool });
        used.add(tool.id);
      }
      replies.filter(r => r.tool_call_id === call.id).forEach(addReply);
    }
    replies.filter(r => !r.tool_call_id && r.anchor_message_id === message.id).forEach(addReply);
  }
  for (const tool of tools) {
    if (!used.has(tool.id)) {
      entries.push({ id: `tool:${tool.id}`, kind: "tool", tool });
      replies.filter(r => r.tool_call_id === tool.id).forEach(addReply);
    }
  }
  replies.forEach(addReply);
  return entries;
}

const toolLabels: Record<string, string> = {
  read_task_context: "读取账单任务", write_todos: "更新处理计划",
  intake_documents: "读取材料并转换 Markdown", prepare_document_extraction: "定位待提取内容",
  read_document_sources: "补读原始材料", read_markdown_evidence: "读取原文证据",
  read_file: "读取文件", grep: "搜索文档内容", glob: "查找文件", ls: "查看材料目录",
  save_document_extraction: "保存提取结果", link_task_evidence: "关联原文证据",
  reconcile_task_charges: "核对费用与财务方向", assess_task_confidence: "核验字段置信度",
  validate_task: "校验账单结果", ask_user: "请求补充信息", task: "委派专家处理",
  execute: "执行命令", shell: "执行命令", run_command: "执行命令",
  record_review_decision: '理解并记录您的回复', prepare_export: '整理账单结果',
};
export function toolLabel(name: string): string {
  return toolLabels[name] || name;
}
export function displayValue(value: unknown): string {
  if (value == null) return "";
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}
export function commandFor(tool: AssembledToolCall): string {
  if (!/^(execute|shell|run_command|exec_command)$/.test(tool.name)) return "";
  const args = tool.args as Record<string, unknown> | null;
  const command = args?.command ?? args?.cmd;
  return typeof command === "string" ? command : "";
}
export function toolContext(tool: AssembledToolCall): string {
  const args = tool.args as Record<string, unknown> | null;
  const value = commandFor(tool) || args?.file_path || args?.path || args?.pattern || args?.source_id || args?.subagent_type;
  return typeof value === "string" ? value : "";
}
