import { useEffect, useState } from "react";
import { api } from "../api";

interface RunOption {
  id: string;
  agent_name: string;
}

interface MetricDiff {
  run_a: number | string;
  run_b: number | string;
  diff?: number;
  pct_change?: number;
}

export default function Compare() {
  const [runs, setRuns] = useState<RunOption[]>([]);
  const [runA, setRunA] = useState("");
  const [runB, setRunB] = useState("");
  const [result, setResult] = useState<Record<string, MetricDiff> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.runs
      .list()
      .then((data) =>
        setRuns(data.map((r) => ({ id: String(r.id), agent_name: String(r.agent_name) })))
      )
      .catch(() => {});
  }, []);

  const handleCompare = async () => {
    if (!runA || !runB) return;
    setLoading(true);
    setError("");
    try {
      const data = await api.compare(runA, runB);
      setResult(data as Record<string, MetricDiff>);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Compare Runs</h1>

      <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-gray-700">Run A</label>
            <select
              value={runA}
              onChange={(e) => setRunA(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            >
              <option value="">-- select run --</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.agent_name} ({r.id.slice(0, 8)})
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-gray-700">Run B</label>
            <select
              value={runB}
              onChange={(e) => setRunB(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            >
              <option value="">-- select run --</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.agent_name} ({r.id.slice(0, 8)})
                </option>
              ))}
            </select>
          </div>
        </div>
        <button
          onClick={handleCompare}
          disabled={!runA || !runB || loading}
          className="px-6 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
        >
          {loading ? "Comparing..." : "Compare"}
        </button>
      </div>

      {error && <p className="text-red-600 mb-4">{error}</p>}

      {result && (
        <div className="overflow-x-auto border border-gray-200 rounded-lg">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Metric
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Run A
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Run B
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Diff
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  % Change
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-100">
              {Object.entries(result).map(([metric, vals]) => (
                <tr key={metric}>
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{metric}</td>
                  <td className="px-4 py-3 text-sm text-gray-700">{String(vals.run_a)}</td>
                  <td className="px-4 py-3 text-sm text-gray-700">{String(vals.run_b)}</td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {vals.diff != null ? (
                      <span className={vals.diff > 0 ? "text-green-600" : vals.diff < 0 ? "text-red-600" : ""}>
                        {vals.diff > 0 ? "+" : ""}
                        {typeof vals.diff === "number" ? vals.diff.toFixed(2) : vals.diff}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {vals.pct_change != null ? `${vals.pct_change.toFixed(1)}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
