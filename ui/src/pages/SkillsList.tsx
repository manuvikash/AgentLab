import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createColumnHelper } from "@tanstack/react-table";
import { api } from "../api";
import DataTable from "../components/DataTable";
import type { SkillDocument } from "../types";

const col = createColumnHelper<SkillDocument>();

const columns = [
  col.accessor("id", {
    header: "ID",
    cell: (info) => <span className="font-medium text-indigo-600">{info.getValue()}</span>,
  }),
  col.accessor("name", {
    header: "Name",
    cell: (info) => <span className="font-medium text-gray-900">{info.getValue() || "—"}</span>,
  }),
  col.accessor("description", {
    header: "Description",
    cell: (info) => (
      <span className="block max-w-lg truncate text-gray-600" title={info.getValue()}>
        {info.getValue() || "—"}
      </span>
    ),
  }),
];

export default function SkillsList() {
  const [skills, setSkills] = useState<SkillDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.skills
      .list()
      .then((data) => setSkills(data as unknown as SkillDocument[]))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Skills</h1>
          <p className="text-sm text-gray-500 mt-1">
            SKILL.md files with frontmatter (name, description) and progressive disclosure via{" "}
            <code className="text-xs bg-gray-100 px-1 rounded">load_skill</code>.
          </p>
        </div>
        <Link
          to="/skills/new"
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition-colors"
        >
          New Skill
        </Link>
      </div>
      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <DataTable
          data={skills}
          columns={columns}
          searchPlaceholder="Search skills..."
          onRowClick={(row) => navigate(`/skills/${row.id}`)}
        />
      )}
    </div>
  );
}
