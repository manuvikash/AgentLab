import { useEffect, useState } from "react";
import { api } from "../api";

interface CompEntry {
  type: string;
  name: string;
  class: string;
}

export default function ComponentsList() {
  const [components, setComponents] = useState<CompEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.components
      .list()
      .then((data) => setComponents(data as unknown as CompEntry[]))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const grouped = components.reduce<Record<string, CompEntry[]>>((acc, c) => {
    (acc[c.type] ??= []).push(c);
    return acc;
  }, {});

  const typeColors: Record<string, string> = {
    llm: "border-indigo-300 bg-indigo-50",
    loop: "border-emerald-300 bg-emerald-50",
    context: "border-amber-300 bg-amber-50",
    tool: "border-purple-300 bg-purple-50",
    sandbox: "border-rose-300 bg-rose-50",
    memory: "border-teal-300 bg-teal-50",
  };

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Components</h1>
      <p className="text-sm text-gray-500 mb-6">Registered component implementations from the Python registry.</p>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([type, items]) => (
            <div key={type}>
              <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wider mb-2">
                {type} ({items.length})
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {items.map((c) => (
                  <div
                    key={`${c.type}-${c.name}`}
                    className={`border rounded-lg p-4 ${typeColors[type] || "border-gray-200 bg-white"}`}
                  >
                    <p className="font-medium text-gray-900 truncate" title={c.name}>
                      {c.name}
                    </p>
                    <p
                      className="text-xs text-gray-500 mt-1 font-mono truncate"
                      title={c.class}
                    >
                      {c.class}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
