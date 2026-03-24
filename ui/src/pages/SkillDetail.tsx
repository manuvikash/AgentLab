import { useCallback, useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import JsonViewer from "../components/JsonViewer";
import SkillBundleTree from "../components/SkillBundleTree";
import type { SkillDocument, SkillFileNode } from "../types";

export default function SkillDetail() {
  const { id } = useParams<{ id: string }>();
  const [skill, setSkill] = useState<SkillDocument | null>(null);
  const [error, setError] = useState("");
  const [fileTree, setFileTree] = useState<SkillFileNode | null>(null);
  const [treeError, setTreeError] = useState("");
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    if (!id) return;
    setError("");
    setTreeError("");
    setFileTree(null);
    setSelectedPath(null);
    setPreview(null);
    setPreviewError("");
    api.skills
      .get(id)
      .then((data) => setSkill(data as unknown as SkillDocument))
      .catch((e) => setError(e.message));
    api.skills
      .fileTree(id)
      .then((data) => setFileTree(data as unknown as SkillFileNode))
      .catch((e) => setTreeError(e.message));
  }, [id]);

  const loadPreview = useCallback(
    async (path: string) => {
      if (!id) return;
      setSelectedPath(path);
      setPreviewLoading(true);
      setPreviewError("");
      setPreview(null);
      try {
        const res = await api.skills.fileContent(id, path);
        setPreview(res.content);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setPreviewError(msg);
      } finally {
        setPreviewLoading(false);
      }
    },
    [id]
  );

  const handleDelete = async () => {
    if (!id || !confirm(`Delete skill "${id}"? This removes skills/${id}/SKILL.md.`)) return;
    await api.skills.delete(id);
    navigate("/skills");
  };

  if (error) return <p className="text-red-600">{error}</p>;
  if (!skill) return <p className="text-gray-500">Loading...</p>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to="/skills" className="text-sm text-indigo-600 hover:underline">
            &larr; Skills
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-1 font-mono">{skill.id}</h1>
          {skill.name && <p className="text-lg text-gray-700 mt-1">{skill.name}</p>}
        </div>
        <div className="flex gap-2">
          <Link
            to={`/skills/${id}/edit`}
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
          <h3 className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-2">Description</h3>
          <p className="text-sm text-gray-800 whitespace-pre-wrap">{skill.description || "—"}</p>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-3">Bundle</h3>
          {treeError ? (
            <p className="text-sm text-amber-700">{treeError}</p>
          ) : !fileTree ? (
            <p className="text-sm text-gray-500">Loading file list…</p>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="border border-gray-100 rounded-lg bg-gray-50/80 p-3 max-h-[min(70vh,520px)] overflow-y-auto">
                <SkillBundleTree root={fileTree} selectedPath={selectedPath} onSelectFile={loadPreview} />
              </div>
              <div className="border border-gray-100 rounded-lg bg-gray-50 min-h-[120px] max-h-[min(70vh,520px)] overflow-hidden flex flex-col">
                <div className="text-xs text-gray-500 px-3 py-2 border-b border-gray-100 bg-white shrink-0">
                  {selectedPath ? (
                    <span className="font-mono text-gray-700 break-all">{selectedPath}</span>
                  ) : (
                    <span>Select a file to preview</span>
                  )}
                </div>
                <div className="flex-1 overflow-y-auto p-3 text-sm">
                  {previewLoading && <p className="text-gray-500">Loading…</p>}
                  {!previewLoading && previewError && (
                    <p className="text-red-600 whitespace-pre-wrap text-xs font-mono">{previewError}</p>
                  )}
                  {!previewLoading && !previewError && preview !== null && (
                    <pre className="whitespace-pre-wrap font-mono text-xs text-gray-800">{preview}</pre>
                  )}
                  {!previewLoading && !previewError && preview === null && selectedPath === null && (
                    <p className="text-gray-500 text-sm">Click any file in the tree.</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-2">Instructions (body)</h3>
          <pre className="text-sm text-gray-800 whitespace-pre-wrap font-sans bg-gray-50 rounded-lg p-4 border border-gray-100 max-h-[480px] overflow-y-auto">
            {skill.body || "—"}
          </pre>
        </div>
      </div>

      <JsonViewer data={skill} title="Raw skill JSON" />
    </div>
  );
}
