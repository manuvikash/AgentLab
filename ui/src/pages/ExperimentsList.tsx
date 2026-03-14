import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createColumnHelper } from "@tanstack/react-table";
import { api } from "../api";
import DataTable from "../components/DataTable";
import StatusBadge from "../components/StatusBadge";
import type { ExperimentRecord } from "../types";

const col = createColumnHelper<ExperimentRecord>();

const columns = [
  col.accessor("name", {
    header: "Name",
    cell: (info) => <span className="font-medium text-indigo-600">{info.getValue()}</span>,
  }),
  col.accessor("id", {
    header: "ID",
    cell: (info) => <span className="font-mono text-xs text-gray-500">{info.getValue().slice(0, 12)}...</span>,
  }),
  col.accessor("status", {
    header: "Status",
    cell: (info) => <StatusBadge status={info.getValue()} />,
  }),
  col.accessor("run_ids", {
    header: "Runs",
    cell: (info) => info.getValue().length,
  }),
  col.accessor("created_at", {
    header: "Created",
    cell: (info) => new Date(info.getValue()).toLocaleString(),
  }),
];

export default function ExperimentsList() {
  const [experiments, setExperiments] = useState<ExperimentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.experiments
      .list()
      .then((data) => setExperiments(data as unknown as ExperimentRecord[]))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Experiments</h1>
        <Link
          to="/experiments/new"
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition-colors"
        >
          New Experiment
        </Link>
      </div>
      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <DataTable
          data={experiments}
          columns={columns}
          searchPlaceholder="Search experiments..."
          onRowClick={(exp) => navigate(`/experiments/${exp.id}`)}
        />
      )}
    </div>
  );
}
