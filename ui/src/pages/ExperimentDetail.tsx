import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { createColumnHelper } from "@tanstack/react-table";
import { api } from "../api";
import StatusBadge from "../components/StatusBadge";
import JsonViewer from "../components/JsonViewer";
import DataTable from "../components/DataTable";
import type { RunRecord } from "../types";

const col = createColumnHelper<RunRecord>();

const runColumns = [
  col.accessor("id", {
    header: "Run ID",
    cell: (info) => <span className="font-mono text-xs">{info.getValue().slice(0, 12)}...</span>,
  }),
  col.accessor("agent_name", { header: "Agent" }),
  col.accessor("status", {
    header: "Status",
    cell: (info) => <StatusBadge status={info.getValue()} />,
  }),
  col.accessor("metrics", {
    id: "steps",
    header: "Steps",
    cell: (info) => info.getValue().steps,
  }),
  col.accessor("metrics", {
    id: "tokens",
    header: "Tokens",
    cell: (info) => info.getValue().tokens_used.toLocaleString(),
  }),
  col.accessor("metrics", {
    id: "success",
    header: "Success",
    cell: (info) => {
      const v = info.getValue().success;
      return v === true ? "Yes" : v === false ? "No" : "—";
    },
  }),
];

export default function ExperimentDetail() {
  const { id } = useParams<{ id: string }>();
  const [experiment, setExperiment] = useState<Record<string, unknown> | null>(null);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    if (!id) return;
    api.experiments
      .get(id)
      .then((data) => {
        setExperiment(data);
        if (Array.isArray(data.runs)) {
          setRuns(data.runs as unknown as RunRecord[]);
        }
      })
      .catch((e) => setError(e.message));
  }, [id]);

  const handleDelete = async () => {
    if (!id || !confirm("Delete this experiment?")) return;
    await api.experiments.delete(id);
    navigate("/experiments");
  };

  if (error) return <p className="text-red-600">{error}</p>;
  if (!experiment) return <p className="text-gray-500">Loading...</p>;

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to="/experiments" className="text-sm text-indigo-600 hover:underline">
            &larr; Experiments
          </Link>
          <div className="flex items-center gap-3 mt-1">
            <h1 className="text-2xl font-bold text-gray-900">{String(experiment.name)}</h1>
            <StatusBadge status={String(experiment.status)} />
          </div>
        </div>
        <button
          onClick={handleDelete}
          className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 transition-colors"
        >
          Delete
        </button>
      </div>

      <div className="mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Runs ({runs.length})</h2>
        <DataTable
          data={runs}
          columns={runColumns}
          onRowClick={(run) => navigate(`/runs/${run.id}`)}
        />
      </div>

      <JsonViewer data={experiment.config || {}} title="Experiment Config" />
      <div className="mt-4">
        <JsonViewer data={experiment} title="Raw Experiment JSON" />
      </div>
    </div>
  );
}
