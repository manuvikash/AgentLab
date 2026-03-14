import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

interface Counts {
  agents: number;
  runs: number;
  experiments: number;
  tasks: number;
}

export default function Dashboard() {
  const [counts, setCounts] = useState<Counts>({ agents: 0, runs: 0, experiments: 0, tasks: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.agents.list(),
      api.runs.list(),
      api.experiments.list(),
      api.tasks.list(),
    ]).then(([agents, runs, experiments, tasks]) => {
      setCounts({
        agents: agents.length,
        runs: runs.length,
        experiments: experiments.length,
        tasks: tasks.length,
      });
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const cards = [
    { label: "Agents", count: counts.agents, href: "/agents", color: "bg-indigo-500" },
    { label: "Runs", count: counts.runs, href: "/runs", color: "bg-emerald-500" },
    { label: "Experiments", count: counts.experiments, href: "/experiments", color: "bg-amber-500" },
    { label: "Tasks", count: counts.tasks, href: "/tasks", color: "bg-rose-500" },
  ];

  const quickActions = [
    { label: "New Agent", href: "/agents/new" },
    { label: "New Task", href: "/tasks/new" },
    { label: "New Experiment", href: "/experiments/new" },
    { label: "Compare Runs", href: "/compare" },
  ];

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {cards.map((c) => (
              <Link
                key={c.label}
                to={c.href}
                className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow"
              >
                <div className={`w-10 h-10 ${c.color} rounded-lg flex items-center justify-center text-white font-bold text-lg mb-3`}>
                  {c.count}
                </div>
                <p className="text-sm font-medium text-gray-700">{c.label}</p>
              </Link>
            ))}
          </div>

          <h2 className="text-lg font-semibold text-gray-800 mb-3">Quick Actions</h2>
          <div className="flex flex-wrap gap-3">
            {quickActions.map((a) => (
              <Link
                key={a.label}
                to={a.href}
                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition-colors"
              >
                {a.label}
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
