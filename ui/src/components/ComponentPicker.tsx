import { useEffect, useState } from "react";
import { api } from "../api";

interface Props {
  componentType: string;
  value: string;
  onChange: (val: string) => void;
  label: string;
}

export default function ComponentPicker({ componentType, value, onChange, label }: Props) {
  const [options, setOptions] = useState<string[]>([]);

  useEffect(() => {
    api.components
      .byType(componentType)
      .then((items) => {
        const names = items.map((c) => String(c.name || c.class || ""));
        setOptions(names);
      })
      .catch(() => setOptions([]));
  }, [componentType]);

  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
      >
        <option value="">-- select --</option>
        {options.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
    </div>
  );
}
