import type { SkillFileNode } from "../types";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function TreeNode({
  node,
  selectedPath,
  onSelectFile,
}: {
  node: SkillFileNode;
  selectedPath: string | null;
  onSelectFile: (path: string) => void;
}) {
  if (node.kind === "file") {
    const active = selectedPath === node.path;
    return (
      <li className="flex items-baseline gap-2 py-0.5 pl-0">
        <button
          type="button"
          className={`text-left truncate min-w-0 flex-1 rounded px-1 py-0.5 -mx-1 transition-colors ${
            active ? "bg-indigo-100 text-indigo-900" : "text-indigo-700 hover:bg-gray-100"
          }`}
          onClick={() => onSelectFile(node.path)}
        >
          {node.name}
        </button>
        <span className="text-gray-400 text-xs shrink-0 tabular-nums">{formatBytes(node.size ?? 0)}</span>
      </li>
    );
  }

  return (
    <li>
      <details open className="group">
        <summary className="cursor-pointer text-gray-800 font-medium py-0.5 list-none [&::-webkit-details-marker]:hidden flex items-center gap-1">
          <span className="text-gray-400 text-xs w-3 shrink-0 group-open:rotate-90 transition-transform">▸</span>
          <span>{node.name}/</span>
        </summary>
        <ul className="pl-3 ml-1 border-l border-gray-200 mt-1 space-y-0.5">
          {(node.children ?? []).map((child) => (
            <TreeNode
              key={child.path || child.name}
              node={child}
              selectedPath={selectedPath}
              onSelectFile={onSelectFile}
            />
          ))}
        </ul>
      </details>
    </li>
  );
}

export default function SkillBundleTree({
  root,
  selectedPath,
  onSelectFile,
}: {
  root: SkillFileNode;
  selectedPath: string | null;
  onSelectFile: (path: string) => void;
}) {
  return (
    <ul className="text-sm font-mono space-y-0.5">
      {(root.children ?? []).map((child) => (
        <TreeNode
          key={child.path || child.name}
          node={child}
          selectedPath={selectedPath}
          onSelectFile={onSelectFile}
        />
      ))}
    </ul>
  );
}
