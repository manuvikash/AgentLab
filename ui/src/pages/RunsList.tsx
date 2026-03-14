import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createColumnHelper } from "@tanstack/react-table";
import { api } from "../api";
import DataTable from "../components/DataTable";
import StatusBadge from "../components/StatusBadge";
import type { RunRecord } from "../types";

const col = createColumnHelper<RunRecord>();

const columns = [
  col.accessor("id", {
    header: "Run ID",
    cell: (info) => (
      <span className="font-mono text-xs text-indigo-600">{info.getValue().slice(0, 12)}...</span>
    ),
  }),
  col.accessor("agent_name", { header: "Agent" }),
  col.accessor("task_id", {
    header: "Task",
    cell: (info) => info.getValue() || "—",
  }),
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
    id: "runtime",
    header: "Runtime",
    cell: (info) => `${info.getValue().runtime_seconds.toFixed(1)}s`,
  }),
  col.accessor("created_at", {
    header: "Created",
    cell: (info) => new Date(info.getValue()).toLocaleString(),
  }),
];

export default function RunsList() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.runs
      .list()
      .then((data) => setRuns(data as unknown as RunRecord[]))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Runs</h1>
      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <DataTable
          data={runs}
          columns={columns}
          searchPlaceholder="Search runs..."
          onRowClick={(run) => navigate(`/runs/${run.id}`)}
        />
      )}
    </div>
  );
}
