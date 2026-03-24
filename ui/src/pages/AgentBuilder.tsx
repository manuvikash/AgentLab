import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api } from "../api";
import FormField from "../components/FormField";
import ComponentPicker from "../components/ComponentPicker";

export default function AgentBuilder() {
  const { name } = useParams<{ name: string }>();
  const isEdit = !!name;
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: "",
    llm: "openai",
    loop: "react",
    context: "simple",
    sandbox: "local",
    memory: "",
    prompt: "",
    max_steps: 10,
    max_tokens: 4096,
    tools: [] as string[],
    skills: [] as string[],
  });

  const [toolOptions, setToolOptions] = useState<{ value: string; label: string }[]>([]);
  const [skillOptions, setSkillOptions] = useState<{ value: string; label: string }[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.components
      .byType("tool")
      .then((items) =>
        setToolOptions(
          items
            .filter((c) => String(c.name) !== "load_skill")
            .map((c) => ({ value: String(c.name), label: String(c.name) }))
        )
      )
      .catch(() => {});
  }, []);

  useEffect(() => {
    api.skills
      .list()
      .then((items) =>
        setSkillOptions(
          items.map((s) => ({
            value: String(s.id),
            label: `${String(s.id)} — ${String(s.name || s.id)}`,
          }))
        )
      )
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!isEdit) return;
    api.agents
      .get(name!)
      .then((data) => {
        const a = data as Record<string, unknown>;
        setForm({
          name: String(a.name || ""),
          llm: String(a.llm || ""),
          loop: String(a.loop || ""),
          context: String(a.context || ""),
          sandbox: String(a.sandbox || ""),
          memory: String(a.memory || ""),
          prompt: String(a.prompt || ""),
          max_steps: Number(a.max_steps || 10),
          max_tokens: Number(a.max_tokens || 4096),
          tools: Array.isArray(a.tools) ? (a.tools as string[]) : [],
          skills: Array.isArray(a.skills) ? (a.skills as string[]) : [],
        });
      })
      .catch(() => {});
  }, [name, isEdit]);

  const handleSave = async () => {
    setSaving(true);
    const payload = {
      ...form,
      memory: form.memory || null,
      prompt: form.prompt || null,
      skills: form.skills,
    };
    try {
      if (isEdit) {
        await api.agents.update(name!, payload);
      } else {
        await api.agents.create(payload);
      }
      navigate(`/agents/${form.name}`);
    } catch (e) {
      alert(String(e));
    } finally {
      setSaving(false);
    }
  };

  const set = (key: string) => (val: string) =>
    setForm((f) => ({ ...f, [key]: key === "max_steps" || key === "max_tokens" ? Number(val) || 0 : val }));

  return (
    <div className="max-w-2xl mx-auto">
      <Link to="/agents" className="text-sm text-indigo-600 hover:underline">
        &larr; Agents
      </Link>
      <h1 className="text-2xl font-bold text-gray-900 mt-2 mb-6">
        {isEdit ? `Edit ${name}` : "New Agent"}
      </h1>

      <div className="space-y-5 bg-white border border-gray-200 rounded-xl p-6">
        <FormField label="Name" type="text" value={form.name} onChange={set("name")} placeholder="my_agent" />

        <div className="grid grid-cols-2 gap-4">
          <ComponentPicker componentType="llm" value={form.llm} onChange={set("llm")} label="LLM" />
          <ComponentPicker componentType="loop" value={form.loop} onChange={set("loop")} label="Loop" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <ComponentPicker componentType="context" value={form.context} onChange={set("context")} label="Context Manager" />
          <ComponentPicker componentType="sandbox" value={form.sandbox} onChange={set("sandbox")} label="Sandbox" />
        </div>

        <ComponentPicker componentType="memory" value={form.memory} onChange={set("memory")} label="Memory (optional)" />

        <FormField
          label="Tools"
          type="multi-select"
          value={form.tools}
          onChange={(val) => setForm((f) => ({ ...f, tools: val }))}
          options={toolOptions}
        />

        <FormField
          label="Skills (catalog + load_skill)"
          type="multi-select"
          value={form.skills}
          onChange={(val) => setForm((f) => ({ ...f, skills: val }))}
          options={skillOptions}
        />

        <FormField label="System Prompt" type="textarea" value={form.prompt} onChange={set("prompt")} placeholder="You are a helpful agent..." />

        <div className="grid grid-cols-2 gap-4">
          <FormField label="Max Steps" type="number" value={form.max_steps} onChange={set("max_steps")} />
          <FormField label="Max Tokens" type="number" value={form.max_tokens} onChange={set("max_tokens")} />
        </div>

        <button
          onClick={handleSave}
          disabled={saving || !form.name}
          className="w-full py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
        >
          {saving ? "Saving..." : isEdit ? "Update Agent" : "Create Agent"}
        </button>
      </div>
    </div>
  );
}
