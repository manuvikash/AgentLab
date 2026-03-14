import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api } from "../api";
import FormField from "../components/FormField";

export default function TaskBuilder() {
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const navigate = useNavigate();

  const [form, setForm] = useState({
    id: "",
    prompt: "",
    repo: "",
    validator: "",
    setup_commands: [""],
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isEdit) return;
    api.tasks
      .get(id!)
      .then((data) => {
        const t = data as Record<string, unknown>;
        setForm({
          id: String(t.id || ""),
          prompt: String(t.prompt || ""),
          repo: String(t.repo || ""),
          validator: String(t.validator || ""),
          setup_commands: Array.isArray(t.setup_commands) && t.setup_commands.length > 0
            ? (t.setup_commands as string[])
            : [""],
        });
      })
      .catch(() => {});
  }, [id, isEdit]);

  const handleSave = async () => {
    setSaving(true);
    const payload = {
      ...form,
      repo: form.repo || null,
      validator: form.validator || null,
      setup_commands: form.setup_commands.filter((s) => s.trim()),
    };
    try {
      if (isEdit) {
        await api.tasks.update(id!, payload);
      } else {
        await api.tasks.create(payload);
      }
      navigate(`/tasks/${form.id}`);
    } catch (e) {
      alert(String(e));
    } finally {
      setSaving(false);
    }
  };

  const set = (key: string) => (val: string) =>
    setForm((f) => ({ ...f, [key]: val }));

  const updateCmd = (idx: number, val: string) => {
    setForm((f) => {
      const cmds = [...f.setup_commands];
      cmds[idx] = val;
      return { ...f, setup_commands: cmds };
    });
  };

  const addCmd = () => setForm((f) => ({ ...f, setup_commands: [...f.setup_commands, ""] }));
  const removeCmd = (idx: number) =>
    setForm((f) => ({ ...f, setup_commands: f.setup_commands.filter((_, i) => i !== idx) }));

  return (
    <div className="max-w-2xl mx-auto">
      <Link to="/tasks" className="text-sm text-indigo-600 hover:underline">
        &larr; Tasks
      </Link>
      <h1 className="text-2xl font-bold text-gray-900 mt-2 mb-6">
        {isEdit ? `Edit ${id}` : "New Task"}
      </h1>

      <div className="space-y-5 bg-white border border-gray-200 rounded-xl p-6">
        <FormField label="Task ID" type="text" value={form.id} onChange={set("id")} placeholder="bug_fix_1" />
        <FormField label="Prompt" type="textarea" value={form.prompt} onChange={set("prompt")} placeholder="Fix the bug in..." />
        <FormField label="Repo Path" type="text" value={form.repo} onChange={set("repo")} placeholder="repo" hint="Relative path to task repository" />
        <FormField label="Validator Command" type="text" value={form.validator} onChange={set("validator")} placeholder="python -m pytest tests/" />

        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-gray-700">Setup Commands</label>
          <div className="space-y-2">
            {form.setup_commands.map((cmd, i) => (
              <div key={i} className="flex gap-2">
                <input
                  type="text"
                  value={cmd}
                  onChange={(e) => updateCmd(i, e.target.value)}
                  placeholder="pip install -r requirements.txt"
                  className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                />
                {form.setup_commands.length > 1 && (
                  <button
                    onClick={() => removeCmd(i)}
                    className="px-2 text-red-500 hover:text-red-700 text-lg"
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
            <button onClick={addCmd} className="text-sm text-indigo-600 hover:underline">
              + Add command
            </button>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saving || !form.id || !form.prompt}
          className="w-full py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
        >
          {saving ? "Saving..." : isEdit ? "Update Task" : "Create Task"}
        </button>
      </div>
    </div>
  );
}
