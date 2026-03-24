import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api } from "../api";
import FormField from "../components/FormField";

export default function SkillBuilder() {
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const navigate = useNavigate();

  const [form, setForm] = useState({
    id: "",
    name: "",
    description: "",
    body: "",
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isEdit) return;
    api.skills
      .get(id!)
      .then((data) => {
        const s = data as Record<string, unknown>;
        setForm({
          id: String(s.id || ""),
          name: String(s.name || ""),
          description: String(s.description || ""),
          body: String(s.body || ""),
        });
      })
      .catch(() => {});
  }, [id, isEdit]);

  const handleSave = async () => {
    setSaving(true);
    const payload = {
      id: form.id,
      name: form.name,
      description: form.description,
      body: form.body,
    };
    try {
      if (isEdit) {
        await api.skills.update(id!, payload);
      } else {
        await api.skills.create(payload);
      }
      navigate(`/skills/${form.id}`);
    } catch (e) {
      alert(String(e));
    } finally {
      setSaving(false);
    }
  };

  const set = (key: string) => (val: string) =>
    setForm((f) => ({ ...f, [key]: val }));

  return (
    <div className="max-w-2xl mx-auto">
      <Link to={isEdit ? `/skills/${id}` : "/skills"} className="text-sm text-indigo-600 hover:underline">
        &larr; {isEdit ? `Skill ${id}` : "Skills"}
      </Link>
      <h1 className="text-2xl font-bold text-gray-900 mt-2 mb-6">
        {isEdit ? `Edit ${id}` : "New Skill"}
      </h1>

      <div className="space-y-5 bg-white border border-gray-200 rounded-xl p-6">
        <FormField
          label="Skill ID"
          type="text"
          value={form.id}
          onChange={set("id")}
          placeholder="my_skill"
          hint="Directory name under skills/; use letters, numbers, underscores, hyphens."
          disabled={isEdit}
        />
        <FormField
          label="Name"
          type="text"
          value={form.name}
          onChange={set("name")}
          placeholder="Short display name (YAML frontmatter)"
        />
        <FormField
          label="Description"
          type="textarea"
          value={form.description}
          onChange={set("description")}
          placeholder="When to use this skill — shown in the agent catalog only."
        />
        <FormField
          label="Instructions (markdown body)"
          type="textarea"
          value={form.body}
          onChange={set("body")}
          placeholder="Full instructions loaded when the agent calls load_skill."
          rows={14}
        />

        <button
          onClick={handleSave}
          disabled={saving || !form.id.trim()}
          className="w-full py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
        >
          {saving ? "Saving..." : isEdit ? "Update Skill" : "Create Skill"}
        </button>
      </div>
    </div>
  );
}
