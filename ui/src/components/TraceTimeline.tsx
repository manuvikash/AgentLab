import { useState } from "react";
import type { TraceEntry } from "../types";

function StepCard({ entry }: { entry: TraceEntry }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative pl-8 pb-6">
      <div className="absolute left-3 top-1.5 w-2.5 h-2.5 rounded-full bg-indigo-500 ring-4 ring-white" />
      {entry.step > 0 && (
        <div className="absolute left-[17px] -top-6 w-px h-6 bg-gray-200" />
      )}
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left bg-white border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow"
      >
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-900">Step {entry.step + 1}</span>
          <div className="flex items-center gap-3 text-xs text-gray-500">
            {entry.token_usage && (
              <span>{entry.token_usage.input_tokens + entry.token_usage.output_tokens} tok</span>
            )}
            <span>{open ? "▾" : "▸"}</span>
          </div>
        </div>
        {entry.thought && (
          <p className="mt-1 text-sm text-gray-600 line-clamp-2">{entry.thought}</p>
        )}
      </button>
      {open && (
        <div className="mt-2 space-y-2 ml-2">
          {entry.thought && (
            <div className="bg-blue-50 rounded p-3">
              <p className="text-xs font-medium text-blue-700 mb-1">Thought</p>
              <p className="text-sm text-blue-900 whitespace-pre-wrap">{entry.thought}</p>
            </div>
          )}
          {entry.action && (
            <div className="bg-amber-50 rounded p-3">
              <p className="text-xs font-medium text-amber-700 mb-1">Action</p>
              <p className="text-sm text-amber-900 whitespace-pre-wrap">{entry.action}</p>
            </div>
          )}
          {entry.tool_call && entry.tool_call.tool === "load_skill" && (
            <div className="bg-teal-50 rounded p-3 border border-teal-100">
              <p className="text-xs font-medium text-teal-800 mb-1">
                Skill loaded
                {(entry.tool_call.skill_name || entry.tool_call.skill_id) && (
                  <span className="font-semibold ml-1">
                    — {entry.tool_call.skill_name || entry.tool_call.skill_id}
                  </span>
                )}
              </p>
              <pre className="text-xs text-teal-900 overflow-x-auto">{JSON.stringify(entry.tool_call.args, null, 2)}</pre>
            </div>
          )}
          {entry.tool_call && entry.tool_call.tool !== "load_skill" && (
            <div className="bg-purple-50 rounded p-3">
              <p className="text-xs font-medium text-purple-700 mb-1">
                Tool: {entry.tool_call.tool}
                {entry.tool_call.duration_ms != null && (
                  <span className="font-normal text-purple-500 ml-2">({entry.tool_call.duration_ms}ms)</span>
                )}
              </p>
              <pre className="text-xs text-purple-900 overflow-x-auto">{JSON.stringify(entry.tool_call.args, null, 2)}</pre>
            </div>
          )}
          {entry.result && (
            <div className="bg-green-50 rounded p-3">
              <p className="text-xs font-medium text-green-700 mb-1">Result</p>
              <p className="text-sm text-green-900 whitespace-pre-wrap break-all">{entry.result}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function TraceTimeline({ trace }: { trace: TraceEntry[] }) {
  if (!trace.length) {
    return <p className="text-gray-500 text-sm">No trace entries.</p>;
  }
  return (
    <div className="relative">
      <div className="absolute left-[17px] top-4 bottom-4 w-px bg-gray-200" />
      {trace.map((entry) => (
        <StepCard key={entry.step} entry={entry} />
      ))}
    </div>
  );
}
