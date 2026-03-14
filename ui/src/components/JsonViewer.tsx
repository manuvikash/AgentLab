import { useState } from "react";
import { JsonView, defaultStyles } from "react-json-view-lite";
import "react-json-view-lite/dist/index.css";

interface Props {
  data: unknown;
  title?: string;
  defaultExpanded?: boolean;
}

export default function JsonViewer({ data, title, defaultExpanded = false }: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {title && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors"
        >
          {title}
          <span className="text-gray-400">{expanded ? "▾" : "▸"}</span>
        </button>
      )}
      {(expanded || !title) && (
        <div className="p-4 bg-white overflow-x-auto text-sm">
          <JsonView
            data={data as object}
            style={{ ...defaultStyles, container: "font-mono text-xs" }}
            shouldExpandNode={(level) => level < 2}
          />
        </div>
      )}
    </div>
  );
}
