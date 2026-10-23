"""Host configuration schemas; business contracts remain in Skills."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints


Name = Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')]


SkillName = Annotated[str, StringConstraints(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', max_length=64)]


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


Count = Annotated[int, Field(strict=True, ge=1)]


Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]


REQUIRED_HOOKS = {'schema', 'coverage', 'evidence', 'amount', 'matching', 'update',
                  'posting', 'revision', 'approval', 'capability', 'budget'}


HOST_TOOLS = {'read_task_context', 'validate_task', 'ask_user', 'record_review_decision', 'intake_documents',
    'read_materials',
    'prepare_document_extraction', 'read_markdown_evidence', 'read_document_sources', 'view_source_image', 'save_document_extraction', 'link_task_evidence',
    'reconcile_task_charges', 'assess_task_confidence', 'prepare_export', 'task', 'write_todos', 'read_file', 'ls', 'glob', 'grep'}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Versioned(StrictModel):
    version: Count


class Agent(StrictModel):
    name: Name
    enabled: bool = True
    type: Literal['agent', 'deep-agent']
    description: Text
    skills: list[SkillName]
    prompt: Text
    tools: list[Name] | None = None
    delegation_contract: bool = False


class Agents(Versioned):
    agents: list[Agent]


class ToolBinding(StrictModel):
    function: Annotated[str, StringConstraints(pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')]
    name: Annotated[str, StringConstraints(pattern=r'^[A-Za-z_][A-Za-z0-9_-]*$')] | None = None


class Skill(StrictModel):
    name: SkillName
    enabled: bool = True
    version: Text
    tools: list[ToolBinding] = Field(default_factory=list)


class Skills(Versioned):
    skills: list[Skill]


class Server(StrictModel):
    id: Name
    enabled: bool = True
    url: Text | None = None
    transport: dict | None = None
    description: str | None = None


class MCP(Versioned):
    servers: list[Server]


class Hook(StrictModel):
    name: Name
    enabled: bool = True
    required: bool = False
    priority: Annotated[int, Field(strict=True, ge=0)] = 0
    skill: SkillName | None = None
    function: Annotated[str, StringConstraints(pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')] | None = None
    native: Literal['dispatch-policy', 'shared-budget'] | None = None


class Hooks(Versioned):
    hooks: list[Hook]


class Runtime(Versioned):
    agent_style: Literal['codex', 'legacy'] = 'codex'
    use_reviewed_experiences: bool = True
    graph_recursion_limit: Count = 512
    model_calls: Count
    turn_model_calls: Count = 6
    run_model_calls: Count = 16
    expert_model_calls: Count = 4
    supervisor_reserve: Annotated[int, Field(strict=True, ge=0)] = 2
    tool_calls: Count
    context_edit_trigger: Count = 8000
    context_edit_keep: Count = 3
    active_seconds: Positive
    document_concurrency: Count
    repair_rounds: Annotated[int, Field(strict=True, ge=0)]
    model_timeout: Positive
    max_tokens: Count
    require_export_approval: bool
    confidence_review_threshold: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)] = 80.0
    pdf_pages_per_slice: Count = 20


MODELS = dict(agents=Agents, skills=Skills, mcp=MCP, hooks=Hooks, runtime=Runtime)
