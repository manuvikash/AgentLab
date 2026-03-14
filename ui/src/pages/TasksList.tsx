import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createColumnHelper } from "@tanstack/react-table";
import { api } from "../api";
import DataTable from "../components/DataTable";
import type { TaskConfig } from "../types";

const col = createColumnHelper<TaskConfig>();

const columns = [
  col.accessor("id", {
    header: "ID",
    cell: (info) => <span className="font-medium text-indigo-600">{info.getValue()}</span>,
  }),
  col.accessor("prompt", {
    header: "Prompt",
    cell: (info) => (
      <span className="block max-w-md truncate" title={info.getValue()}>
        {info.getValue()}
      </span>
    ),
  }),
  col.accessor("repo", {
    header: "Repo",
    cell: (info) => info.getValue() || "—",
  }),
  col.accessor("validator", {
    header: "Validator",
    cell: (info) => info.getValue() || "—",
  }),
];

export default function TasksList() {
  const [tasks, setTasks] = useState<TaskConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.tasks
      .list()
      .then((data) => setTasks(data as unknown as TaskConfig[]))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Tasks</h1>
        <Link
          to="/tasks/new"
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition-colors"
        >
          New Task
        </Link>
      </div>
      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <DataTable
          data={tasks}
          columns={columns}
          searchPlaceholder="Search tasks..."
          onRowClick={(task) => navigate(`/tasks/${task.id}`)}
        />
      )}
    </div>
  );
}
