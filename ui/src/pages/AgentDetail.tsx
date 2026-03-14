import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import JsonViewer from "../components/JsonViewer";
import type { AgentConfig } from "../types";

export default function AgentDetail() {
  const { name } = useParams<{ name: string }>();
  const [agent, setAgent] = useState<AgentConfig | null>(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    if (!name) return;
    api.agents
      .get(name)
      .then((data) => setAgent(data as unknown as AgentConfig))
      .catch((e) => setError(e.message));
  }, [name]);

  const handleDelete = async () => {
    if (!name || !confirm(`Delete agent "${name}"?`)) return;
    await api.agents.delete(name);
    navigate("/agents");
  };

  if (error) return <p className="text-red-600">{error}</p>;
  if (!agent) return <p className="text-gray-500">Loading...</p>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to="/agents" className="text-sm text-indigo-600 hover:underline">
            &larr; Agents
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-1">{agent.name}</h1>
        </div>
        <div className="flex gap-2">
          <Link
            to={`/agents/${name}/edit`}
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

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
        {[
          { label: "LLM", value: agent.llm },
          { label: "Loop", value: agent.loop },
          { label: "Context", value: agent.context },
          { label: "Sandbox", value: agent.sandbox },
          { label: "Memory", value: agent.memory || "—" },
          { label: "Max Steps", value: agent.max_steps },
          { label: "Max Tokens", value: agent.max_tokens },
          { label: "Tools", value: agent.tools.join(", ") || "—" },
        ].map((item) => (
          <div key={item.label} className="bg-white border border-gray-200 rounded-lg p-4">
            <dt className="text-xs text-gray-500 font-medium uppercase tracking-wider">{item.label}</dt>
            <dd className="mt-1 text-sm font-medium text-gray-900">{item.value}</dd>
          </div>
        ))}
      </div>

      {agent.prompt && (
        <div className="mb-6">
          <h3 className="text-sm font-medium text-gray-700 mb-2">System Prompt</h3>
          <pre className="bg-white border border-gray-200 rounded-lg p-4 text-sm whitespace-pre-wrap text-gray-800">
            {agent.prompt}
          </pre>
        </div>
      )}

      <JsonViewer data={agent} title="Raw Config JSON" />
    </div>
  );
}
