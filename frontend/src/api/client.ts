import type {
  Artifact,
  Asset,
  ConfigDocument,
  ConfidenceReport,
  Evidence,
  Health,
  ImprovementCandidate,
  ImprovementRegistry,
  ExperienceCard,
  ExperienceReference,
  JsonObject,
  NewTask,
  Revision,
  SourcePreview,
  Task,
  TraceOverview,
  TaskTrace,
} from "../types/contracts";
const prefix = import.meta.env.VITE_API_BASE || "/api";
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
function list<T>(value: T[] | Record<string, T[]>, key: string): T[] {
  return Array.isArray(value) ? value : value[key] || [];
}
function artifactsFrom(taskId: string, value: JsonObject): Artifact[] {
  const names: Record<string, string> = {
    intake: "材料接入结果",
    charges: "费用提取记录",
    coverage: "分块覆盖情况",
    validation: "校验结果",
    events: "任务审计记录",
  };
  return Object.entries(names)
    .filter(([key]) => value[key] != null)
    .map(([key, name]) => ({
      id: taskId + ":" + key,
      kind: key,
      name,
      payload: value[key],
      revision: value.revision as number,
    }));
}
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${prefix}${path}`, {
      ...options,
      headers:
        options.body instanceof FormData
          ? options.headers
          : { "Content-Type": "application/json", ...options.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(0, "暂时无法连接服务，请检查后端是否已启动。");
  }
  const data: unknown = (response.headers.get("content-type") || "").includes(
    "json",
  )
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const item = data as {
      detail?: unknown;
      message?: string;
      issues?: { message?: string; code?: string }[];
    };
    throw new ApiError(
      response.status,
      typeof item?.detail === "string"
        ? item.detail
        : item?.message ||
          item?.issues
            ?.map((issue) => issue.message || issue.code)
            .filter(Boolean)
            .slice(0, 3)
            .join("；") ||
          ([502, 503].includes(response.status)
            ? "后端服务暂不可用，请等待启动完成后重新连接。"
            : `请求未完成（${response.status}）`),
      data,
    );
  }
  return data as T;
}
export const api = {
  skillCatalog: () => request<{ skills: JsonObject[] }>("/extensions/skills"),
  skillResource: (name: string, path = "SKILL.md") =>
    request<{ content: string; path: string }>(
      `/extensions/skills/${encodeURIComponent(name)}/resource?path=${encodeURIComponent(path)}`,
    ),
  importSkill: (file: File, version: number, tools: string) => {
    const body = new FormData();
    body.append("file", file);
    body.append("expected_version", String(version));
    body.append("tools", tools);
    return request<{ config: JsonObject }>("/extensions/skills/import", {
      method: "POST",
      body,
    });
  },
  testMcp: (server: JsonObject) =>
    request<{ ok: boolean; tools: JsonObject[] }>("/config/mcp/test", {
      method: "POST",
      body: JSON.stringify({ server }),
    }),
  callMcp: (server_id: string, tool: string, args: JsonObject) =>
    request<JsonObject>("/config/mcp/call", {
      method: "POST",
      body: JSON.stringify({ server_id, tool, arguments: args }),
    }),
  evaluationDatasets: () =>
    request<{ datasets: JsonObject[] }>("/improvements/datasets"),
  evaluationDataset: (id: string) =>
    request<JsonObject>(`/improvements/datasets/${encodeURIComponent(id)}`),
  importEvaluationDataset: (value: JsonObject) =>
    request<JsonObject>("/improvements/datasets", {
      method: "POST",
      body: JSON.stringify(value),
    }),
  toggleEvaluationDataset: (id: string, value: JsonObject) =>
    request<JsonObject>(`/improvements/datasets/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(value),
    }),
  activeMapping: (entity: string) =>
    request<{ mapping: Record<string, string>; active_version: string }>(
      `/improvements/mapping?accounting_entity=${encodeURIComponent(entity)}`,
    ),
  reviewConversation: (
    id: string,
    value: {
      expected_revision: number;
      action: string;
      charge_id?: string;
      field?: string;
    },
  ) =>
    request<Task>(`/tasks/${encodeURIComponent(id)}/review-conversation`, {
      method: "POST",
      body: JSON.stringify(value),
    }),
  reply: (
    id: string,
    value: {
      expected_revision: number;
      interrupt_id?: string;
      conversational?: boolean;
      text: string;
      reply_id: string;
    },
  ) =>
    request<Task>(`/tasks/${encodeURIComponent(id)}/reply`, {
      method: "POST",
      body: JSON.stringify(value),
    }),
  confidence: (id: string, signal?: AbortSignal) =>
    request<ConfidenceReport>(`/tasks/${encodeURIComponent(id)}/confidence`, {
      signal,
    }),
  sourcePreview: (
    id: string,
    sourceId: string,
    target: Evidence = {},
    signal?: AbortSignal,
  ) => {
    const query = new URLSearchParams();
    for (const key of [
      "anchor",
      "quote",
      "field",
      "value",
      "charge_id",
    ] as const) {
      if (typeof target[key] === "string" && target[key])
        query.set(key, target[key]);
    }
    return request<SourcePreview>(
      `/tasks/${encodeURIComponent(id)}/sources/${encodeURIComponent(sourceId)}/preview?${query}`,
      { signal },
    );
  },
  health: () => request<Health>("/health"),
  bills: () => request<Task[]>("/bills"),
  deleteTask: (id: string, revision: number) =>
    request<{ id: string; deleted: boolean }>(
      `/tasks/${encodeURIComponent(id)}?expected_revision=${revision}`,
      { method: "DELETE" },
    ),
  traces: () => request<TraceOverview>("/traces"),
  trace: (id: string) =>
    request<TaskTrace>(`/tasks/${encodeURIComponent(id)}/trace`),
  tasks: async () =>
    list(await request<Task[] | { tasks: Task[] }>("/tasks"), "tasks"),
  task: async (id: string) => {
    const task = await request<Task>(`/tasks/${encodeURIComponent(id)}`);
    return {
      ...task,
      artifacts: artifactsFrom(id, task as unknown as JsonObject),
    };
  },
  listAssets: async () =>
    list(await request<Asset[] | { assets: Asset[] }>("/assets"), "assets"),
  samples: async () =>
    list(await request<Asset[] | { assets: Asset[] }>("/samples"), "assets"),
  assets: async (files: File[]) =>
    Promise.all(
      files.map(async (file) => {
        const data = new FormData();
        data.append("file", file);
        return request<Asset>("/assets", { method: "POST", body: data });
      }),
    ),
  importAsset: async (value: { sample_path?: string; url?: string }) => {
    const asset = await request<Asset>("/assets", {
      method: "POST",
      body: JSON.stringify(value),
    });
    return [asset];
  },
  createTask: (value: NewTask) =>
    request<Task>("/tasks", { method: "POST", body: JSON.stringify(value) }),
  revise: (id: string, value: Revision) =>
    request<Task>(`/tasks/${encodeURIComponent(id)}/revision`, {
      method: "PATCH",
      body: JSON.stringify(value),
    }),
  control: (id: string, action: string) =>
    request<Task>(`/tasks/${encodeURIComponent(id)}/control`, {
      method: "POST",
      body: JSON.stringify({ action }),
    }),
  artifacts: async (id: string) =>
    artifactsFrom(
      id,
      await request<JsonObject>(`/tasks/${encodeURIComponent(id)}/artifacts`),
    ),
  export: (id: string, draft = false) =>
    request<JsonObject[]>(
      `/tasks/${encodeURIComponent(id)}/export${draft ? "?draft=true" : ""}`,
    ),
  approve: (
    id: string,
    value: {
      expected_revision: number;
      decision: "approve" | "reject";
      reason: string;
    },
  ) =>
    request<Task>(`/tasks/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      body: JSON.stringify(value),
    }),
  completeReview: (
    id: string,
    value: { expected_revision: number; reason?: string },
  ) =>
    request<Task>(`/tasks/${encodeURIComponent(id)}/complete-review`, {
      method: "POST",
      body: JSON.stringify(value),
    }),
  config: async (kind: string): Promise<ConfigDocument> => {
    const raw = await request<JsonObject>(
      `/config/${encodeURIComponent(kind)}`,
    );
    return { kind, version: raw.version as number, config: raw.config ?? raw };
  },
  saveConfig: async (kind: string, value: unknown): Promise<ConfigDocument> => {
    const raw = await request<JsonObject>(
      `/config/${encodeURIComponent(kind)}`,
      { method: "PUT", body: JSON.stringify(value) },
    );
    return { kind, version: raw.version as number, config: raw.config ?? raw };
  },
  improvements: () =>
    request<{
      candidates: ImprovementCandidate[];
      registry: ImprovementRegistry;
    }>("/improvements/candidates"),
  experiences: () =>
    request<{
      experiences: ExperienceCard[];
      references: ExperienceReference[];
    }>("/improvements/experiences"),
  summarizeExperience: (value: {
    task_id: string;
    expected_revision: number;
    note?: string;
    retry_failed?: boolean;
  }) =>
    request<{ experience: ExperienceCard; reused: boolean }>(
      "/improvements/experiences/summarize",
      {
        method: "POST",
        body: JSON.stringify(value),
      },
    ),
  editExperience: (id: string, value: JsonObject) =>
    request<{ experience: ExperienceCard }>(
      `/improvements/experiences/${encodeURIComponent(id)}`,
      {
        method: "PATCH",
        body: JSON.stringify(value),
      },
    ),
  reviewExperience: (card: ExperienceCard, action: "activate" | "pause") =>
    request<{ experience: ExperienceCard }>(
      `/improvements/experiences/${encodeURIComponent(card.id)}/review`,
      {
        method: "POST",
        body: JSON.stringify({
          expected_revision: card.revision,
          action,
          approved: action === "activate",
        }),
      },
    ),
  proposeImprovement: (value: JsonObject) =>
    request<{ candidate: ImprovementCandidate }>("/improvements/candidates", {
      method: "POST",
      body: JSON.stringify(value),
    }),
  evaluateImprovement: (id: string, dataset_id = "builtin") =>
    request<{ candidate: ImprovementCandidate }>(
      `/improvements/candidates/${encodeURIComponent(id)}/evaluate`,
      { method: "POST", body: JSON.stringify({ dataset_id }) },
    ),
  publishImprovement: (id: string, value: JsonObject) =>
    request<{ candidate: ImprovementCandidate; registry: ImprovementRegistry }>(
      `/improvements/candidates/${encodeURIComponent(id)}/publish`,
      { method: "POST", body: JSON.stringify(value) },
    ),
  rollbackImprovement: (value: JsonObject) =>
    request<{ registry: ImprovementRegistry }>("/improvements/rollback", {
      method: "POST",
      body: JSON.stringify(value),
    }),
};
export function assetUrl(asset: Asset): string {
  return (
    asset.content_url ||
    asset.url ||
    `${prefix}/assets/${encodeURIComponent(asset.id)}/content`
  );
}
export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "操作未完成，请重试。";
}
export function downloadJson(value: unknown, name: string): void {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
