import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import StatusBadge from "../components/StatusBadge";
import MetricsCard from "../components/MetricsCard";
import TraceTimeline from "../components/TraceTimeline";
import JsonViewer from "../components/JsonViewer";
import type { RunRecord, Metrics, TraceEntry } from "../types";

type Tab = "trace" | "metrics" | "config" | "raw";

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<RunRecord | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("trace");
  const navigate = useNavigate();

  useEffect(() => {
    if (!id) return;
    api.runs
      .get(id)
      .then((data) => setRun(data as unknown as RunRecord))
      .catch((e) => setError(e.message));
  }, [id]);

  const handleDelete = async () => {
    if (!id || !confirm("Delete this run?")) return;
    await api.runs.delete(id);
    navigate("/runs");
  };

  if (error) return <p className="text-red-600">{error}</p>;
  if (!run) return <p className="text-gray-500">Loading...</p>;

  const tabs: { key: Tab; label: string }[] = [
    { key: "trace", label: "Trace" },
    { key: "metrics", label: "Metrics" },
    { key: "config", label: "Config" },
    { key: "raw", label: "Raw JSON" },
  ];

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to="/runs" className="text-sm text-indigo-600 hover:underline">
            &larr; Runs
          </Link>
          <div className="flex items-center gap-3 mt-1">
            <h1 className="text-2xl font-bold text-gray-900 font-mono">{run.id.slice(0, 12)}...</h1>
            <StatusBadge status={run.status} />
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Agent: <span className="font-medium text-gray-700">{run.agent_name}</span>
            {run.task_id && (
              <>
                {" · "}Task: <span className="font-medium text-gray-700">{run.task_id}</span>
              </>
            )}
          </p>
        </div>
        <button
          onClick={handleDelete}
          className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 transition-colors"
        >
          Delete
        </button>
      </div>

      {run.error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-sm text-red-800 font-medium">Error</p>
          <p className="text-sm text-red-700 mt-1">{run.error}</p>
        </div>
      )}

      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                tab === t.key
                  ? "border-indigo-500 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {tab === "trace" && <TraceTimeline trace={run.trace as TraceEntry[]} />}
      {tab === "metrics" && <MetricsCard metrics={run.metrics as Metrics} />}
      {tab === "config" && <JsonViewer data={run.agent_config || {}} defaultExpanded />}
      {tab === "raw" && <JsonViewer data={run} defaultExpanded />}
    </div>
  );
}
