const BASE = "/api";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (res.status === 204) return undefined as T;
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

export const api = {
  agents: {
    list: () => request<Record<string, unknown>[]>("/agents"),
    get: (name: string) => request<Record<string, unknown>>(`/agents/${name}`),
    create: (data: unknown) => request("/agents", { method: "POST", body: JSON.stringify(data) }),
    update: (name: string, data: unknown) => request(`/agents/${name}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (name: string) => request(`/agents/${name}`, { method: "DELETE" }),
  },
  runs: {
    list: () => request<Record<string, unknown>[]>("/runs"),
    get: (id: string) => request<Record<string, unknown>>(`/runs/${id}`),
    trace: (id: string) => request<Record<string, unknown>[]>(`/runs/${id}/trace`),
    metrics: (id: string) => request<Record<string, unknown>>(`/runs/${id}/metrics`),
    delete: (id: string) => request(`/runs/${id}`, { method: "DELETE" }),
  },
  experiments: {
    list: () => request<Record<string, unknown>[]>("/experiments"),
    get: (id: string) => request<Record<string, unknown>>(`/experiments/${id}`),
    create: (data: unknown) => request("/experiments", { method: "POST", body: JSON.stringify(data) }),
    delete: (id: string) => request(`/experiments/${id}`, { method: "DELETE" }),
  },
  tasks: {
    list: () => request<Record<string, unknown>[]>("/tasks"),
    get: (id: string) => request<Record<string, unknown>>(`/tasks/${id}`),
    create: (data: unknown) => request("/tasks", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: unknown) => request(`/tasks/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: string) => request(`/tasks/${id}`, { method: "DELETE" }),
  },
  components: {
    list: () => request<Record<string, unknown>[]>("/components"),
    byType: (type: string) => request<Record<string, unknown>[]>(`/components/${type}`),
  },
  compare: (a: string, b: string) => request<Record<string, unknown>>(`/compare/${a}/${b}`),
};
