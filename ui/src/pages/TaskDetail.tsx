import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import JsonViewer from "../components/JsonViewer";
import type { TaskConfig } from "../types";

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>();
  const [task, setTask] = useState<TaskConfig | null>(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    if (!id) return;
    api.tasks
      .get(id)
      .then((data) => setTask(data as unknown as TaskConfig))
      .catch((e) => setError(e.message));
  }, [id]);

  const handleDelete = async () => {
    if (!id || !confirm(`Delete task "${id}"?`)) return;
    await api.tasks.delete(id);
    navigate("/tasks");
  };

  if (error) return <p className="text-red-600">{error}</p>;
  if (!task) return <p className="text-gray-500">Loading...</p>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to="/tasks" className="text-sm text-indigo-600 hover:underline">
            &larr; Tasks
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-1">{task.id}</h1>
        </div>
        <div className="flex gap-2">
          <Link
            to={`/tasks/${id}/edit`}
            className="px-4 py-2 bg-white border border-gray-300 text-sm rounded-lg hover:bg-gray-50 transition-colors"
          >
            Edit
          </Link>
          <button
            onClick={handleDelete}
            className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 transition-colors"
          >
            Delete
          </button>
        </div>
      </div>

      <div className="space-y-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-2">Prompt</h3>
          <p className="text-sm text-gray-800 whitespace-pre-wrap">{task.prompt}</p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <dt className="text-xs text-gray-500 font-medium uppercase tracking-wider">Repo</dt>
            <dd className="mt-1 text-sm text-gray-900">{task.repo || "—"}</dd>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <dt className="text-xs text-gray-500 font-medium uppercase tracking-wider">Validator</dt>
            <dd className="mt-1 text-sm text-gray-900 font-mono">{task.validator || "—"}</dd>
          </div>
        </div>

        {task.setup_commands.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h3 className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-2">Setup Commands</h3>
            <ul className="space-y-1">
              {task.setup_commands.map((cmd, i) => (
                <li key={i} className="text-sm font-mono text-gray-800 bg-gray-50 rounded px-3 py-1.5">
                  {cmd}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <JsonViewer data={task} title="Raw Task JSON" />
    </div>
  );
}
