import type { Metrics } from "../types";

export default function MetricsCard({ metrics }: { metrics: Metrics }) {
  const items = [
    { label: "Status", value: metrics.success ? "Pass" : metrics.success === false ? "Fail" : "N/A", color: metrics.success ? "text-green-600" : "text-red-600" },
    { label: "Steps", value: metrics.steps },
    { label: "Tokens", value: metrics.tokens_used.toLocaleString() },
    { label: "Input Tokens", value: metrics.input_tokens.toLocaleString() },
    { label: "Output Tokens", value: metrics.output_tokens.toLocaleString() },
    { label: "Runtime", value: `${metrics.runtime_seconds.toFixed(1)}s` },
    ...(metrics.patch_size != null ? [{ label: "Patch Size", value: `${metrics.patch_size} bytes` }] : []),
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      {items.map((item) => (
        <div key={item.label} className="bg-white border border-gray-200 rounded-lg p-4">
          <dt className="text-xs text-gray-500 font-medium uppercase tracking-wider">{item.label}</dt>
          <dd className={`mt-1 text-xl font-semibold ${"color" in item ? item.color : "text-gray-900"}`}>
            {item.value}
          </dd>
        </div>
      ))}
    </div>
  );
}
