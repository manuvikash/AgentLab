import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../api";
import FormField from "../components/FormField";

interface MatrixRow {
  type: string;
  values: string[];
}

export default function ExperimentBuilder() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [matrix, setMatrix] = useState<MatrixRow[]>([{ type: "llm", values: [] }]);
  const [baseLlm, setBaseLlm] = useState("openai");
  const [baseLoop, setBaseLoop] = useState("react");
  const [baseContext, setBaseContext] = useState("simple");
  const [tools, setTools] = useState<string[]>([]);
  const [sandbox, setSandbox] = useState("local");
  const [taskId, setTaskId] = useState("");
  const [saving, setSaving] = useState(false);

  const [componentOptions, setComponentOptions] = useState<Record<string, string[]>>({});
  const [taskOptions, setTaskOptions] = useState<{ value: string; label: string }[]>([]);

  const matrixTypes = ["llm", "loop", "context"];

  useEffect(() => {
    const types = [...matrixTypes, "tool", "sandbox"];
    Promise.all(types.map((t) => api.components.byType(t).then((items) => ({ type: t, names: items.map((c) => String(c.name)) })))).then(
      (results) => {
        const opts: Record<string, string[]> = {};
        for (const r of results) opts[r.type] = r.names;
        setComponentOptions(opts);
      }
    );
    api.tasks
      .list()
      .then((items) => setTaskOptions(items.map((t) => ({ value: String(t.id), label: String(t.id) }))))
      .catch(() => {});
  }, []);

  const updateMatrixType = (idx: number, type: string) => {
    setMatrix((m) => m.map((r, i) => (i === idx ? { ...r, type, values: [] } : r)));
  };

  const updateMatrixValues = (idx: number, values: string[]) => {
    setMatrix((m) => m.map((r, i) => (i === idx ? { ...r, values } : r)));
  };

  const addMatrixRow = () => setMatrix((m) => [...m, { type: "llm", values: [] }]);
  const removeMatrixRow = (idx: number) => setMatrix((m) => m.filter((_, i) => i !== idx));

  const handleSave = async () => {
    setSaving(true);
    const matrixObj: Record<string, string[]> = {};
    for (const row of matrix) {
      if (row.values.length > 0) matrixObj[row.type] = row.values;
    }
    const payload = {
      name,
      matrix: matrixObj,
      base: { llm: baseLlm, loop: baseLoop, context: baseContext, tools, sandbox },
      task: taskId || null,
      tasks: taskId ? [taskId] : [],
    };
    try {
      const result = await api.experiments.create(payload);
      // Immediately kick off the run so it doesn't sit in "pending"
      await api.experiments.run(String(result.id));
      navigate(`/experiments/${result.id}`);
    } catch (e) {
      alert(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <Link to="/experiments" className="text-sm text-indigo-600 hover:underline">
        &larr; Experiments
      </Link>
      <h1 className="text-2xl font-bold text-gray-900 mt-2 mb-6">New Experiment</h1>

      <div className="space-y-5 bg-white border border-gray-200 rounded-xl p-6">
        <FormField label="Name" type="text" value={name} onChange={setName} placeholder="compare_llms" />

        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-gray-700">Matrix (parameter sweep)</label>
          <p className="text-xs text-gray-500">Pick component types and select multiple values to sweep over.</p>
          <div className="space-y-3 mt-2">
            {matrix.map((row, idx) => (
              <div key={idx} className="border border-gray-200 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <select
                    value={row.type}
                    onChange={(e) => updateMatrixType(idx, e.target.value)}
                    className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                  >
                    {matrixTypes.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                  {matrix.length > 1 && (
                    <button onClick={() => removeMatrixRow(idx)} className="text-red-500 hover:text-red-700 text-lg ml-auto">
                      ×
                    </button>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {(componentOptions[row.type] || []).map((opt) => {
                    const checked = row.values.includes(opt);
                    return (
                      <label
                        key={opt}
                        className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border cursor-pointer transition-colors ${
                          checked
                            ? "bg-indigo-50 border-indigo-300 text-indigo-700"
                            : "bg-white border-gray-300 text-gray-700 hover:bg-gray-50"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => {
                            const next = checked ? row.values.filter((v) => v !== opt) : [...row.values, opt];
                            updateMatrixValues(idx, next);
                          }}
                          className="sr-only"
                        />
                        {opt}
                      </label>
                    );
                  })}
                </div>
              </div>
            ))}
            <button onClick={addMatrixRow} className="text-sm text-indigo-600 hover:underline">
              + Add dimension
            </button>
          </div>
        </div>

        <div className="border border-gray-200 rounded-lg p-4 space-y-3 bg-gray-50">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Base defaults (used for dimensions not in the matrix)
          </p>
          <div className="grid grid-cols-3 gap-3">
            <FormField
              label="LLM"
              type="select"
              value={baseLlm}
              onChange={setBaseLlm}
              options={(componentOptions.llm || ["openai"]).map((v) => ({ value: v, label: v }))}
            />
            <FormField
              label="Loop"
              type="select"
              value={baseLoop}
              onChange={setBaseLoop}
              options={(componentOptions.loop || ["react"]).map((v) => ({ value: v, label: v }))}
            />
            <FormField
              label="Context"
              type="select"
              value={baseContext}
              onChange={setBaseContext}
              options={(componentOptions.context || ["simple"]).map((v) => ({ value: v, label: v }))}
            />
          </div>
        </div>

        <FormField
          label="Tools"
          type="multi-select"
          value={tools}
          onChange={setTools}
          options={(componentOptions.tool || []).map((t) => ({ value: t, label: t }))}
        />

        <FormField
          label="Sandbox"
          type="select"
          value={sandbox}
          onChange={setSandbox}
          options={(componentOptions.sandbox || []).map((s) => ({ value: s, label: s }))}
        />

        <FormField
          label="Task"
          type="select"
          value={taskId}
          onChange={setTaskId}
          options={taskOptions}
        />

        <button
          onClick={handleSave}
          disabled={saving || !name}
          className="w-full py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
        >
          {saving ? "Saving..." : "Create Experiment"}
        </button>
      </div>
    </div>
  );
}
