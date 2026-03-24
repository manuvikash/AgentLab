export interface SkillDocument {
  id: string;
  name: string;
  description: string;
  body: string;
}

/** Nested bundle listing from GET /skills/:id/files */
export interface SkillFileNode {
  path: string;
  name: string;
  kind: "file" | "dir";
  size?: number;
  children?: SkillFileNode[];
}

export interface AgentConfig {
  name: string;
  llm: string;
  loop: string;
  context: string;
  tools: string[];
  skills?: string[];
  sandbox: string;
  prompt: string | null;
  memory: string | null;
  max_steps: number;
  max_tokens: number;
}

export interface ToolCallRecord {
  tool: string;
  args: Record<string, unknown>;
  result: string | null;
  duration_ms: number | null;
  skill_id: string | null;
  skill_name: string | null;
}

export interface TraceEntry {
  step: number;
  thought: string | null;
  action: string | null;
  tool_call: ToolCallRecord | null;
  result: string | null;
  timestamp: string;
  token_usage: { input_tokens: number; output_tokens: number } | null;
}

export interface Metrics {
  success: boolean | null;
  steps: number;
  tokens_used: number;
  input_tokens: number;
  output_tokens: number;
  runtime_seconds: number;
  patch_size: number | null;
}

export interface RunRecord {
  id: string;
  agent_name: string;
  agent_config: AgentConfig | null;
  task_id: string | null;
  status: "pending" | "running" | "completed" | "failed";
  metrics: Metrics;
  trace: TraceEntry[];
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface TaskConfig {
  id: string;
  prompt: string;
  repo: string | null;
  validator: string | null;
  setup_commands: string[];
}

export interface ExperimentConfig {
  name: string;
  matrix: Record<string, string[]>;
  base: Record<string, unknown>;
  task: string | null;
  tasks: string[];
}

export interface ExperimentRecord {
  id: string;
  name: string;
  config: ExperimentConfig | null;
  run_ids: string[];
  status: string;
  created_at: string;
  completed_at: string | null;
  runs?: RunRecord[];
}

export interface ComponentInfo {
  type: string;
  name: string;
  class: string;
}
