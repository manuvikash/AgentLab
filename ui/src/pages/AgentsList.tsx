import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createColumnHelper } from "@tanstack/react-table";
import { api } from "../api";
import DataTable from "../components/DataTable";
import type { AgentConfig } from "../types";

const col = createColumnHelper<AgentConfig>();

const columns = [
  col.accessor("name", {
    header: "Name",
    cell: (info) => <span className="font-medium text-indigo-600">{info.getValue()}</span>,
  }),
  col.accessor("llm", { header: "LLM" }),
  col.accessor("loop", { header: "Loop" }),
  col.accessor("context", { header: "Context" }),
  col.accessor("sandbox", { header: "Sandbox" }),
  col.accessor("tools", {
    header: "Tools",
    cell: (info) => info.getValue().join(", ") || "—",
  }),
];

export default function AgentsList() {
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.agents
      .list()
      .then((data) => setAgents(data as unknown as AgentConfig[]))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Agents</h1>
        <Link
          to="/agents/new"
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition-colors"
        >
          New Agent
        </Link>
      </div>
      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <DataTable
          data={agents}
          columns={columns}
          searchPlaceholder="Search agents..."
          onRowClick={(agent) => navigate(`/agents/${agent.name}`)}
        />
      )}
    </div>
  );
}
