import type { ReactNode } from "react";

interface BaseProps {
  label: string;
  hint?: string;
  children?: ReactNode;
}

interface InputProps extends BaseProps {
  type: "text" | "number" | "textarea";
  value: string | number;
  onChange: (val: string) => void;
  placeholder?: string;
  disabled?: boolean;
  /** Only used when type is textarea */
  rows?: number;
}

interface SelectProps extends BaseProps {
  type: "select";
  value: string;
  onChange: (val: string) => void;
  options: { value: string; label: string }[];
}

interface MultiSelectProps extends BaseProps {
  type: "multi-select";
  value: string[];
  onChange: (val: string[]) => void;
  options: { value: string; label: string }[];
}

type Props = InputProps | SelectProps | MultiSelectProps;

const inputCls =
  "w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none";

export default function FormField(props: Props) {
  const { label, hint } = props;

  let control: ReactNode;

  if (props.type === "textarea") {
    control = (
      <textarea
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        placeholder={props.placeholder}
        rows={props.type === "textarea" ? (props.rows ?? 4) : 4}
        disabled={"disabled" in props ? props.disabled : false}
        className={`${inputCls} disabled:bg-gray-100 disabled:text-gray-600`}
      />
    );
  } else if (props.type === "select") {
    control = (
      <select
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        className={inputCls}
      >
        <option value="">-- select --</option>
        {props.options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    );
  } else if (props.type === "multi-select") {
    control = (
      <div className="flex flex-wrap gap-2">
        {props.options.map((o) => {
          const checked = props.value.includes(o.value);
          return (
            <label
              key={o.value}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border cursor-pointer transition-colors ${
                checked
                  ? "bg-indigo-50 border-indigo-300 text-indigo-700"
                  : "bg-white border-gray-300 text-gray-700 hover:bg-gray-50"
              }`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => {
                  const next = checked
                    ? props.value.filter((v) => v !== o.value)
                    : [...props.value, o.value];
                  props.onChange(next);
                }}
                className="sr-only"
              />
              {o.label}
            </label>
          );
        })}
      </div>
    );
  } else {
    control = (
      <input
        type={props.type}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        placeholder={props.placeholder}
        disabled={"disabled" in props ? props.disabled : false}
        className={`${inputCls} disabled:bg-gray-100 disabled:text-gray-600`}
      />
    );
  }

  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      {hint && <p className="text-xs text-gray-500">{hint}</p>}
      {control}
    </div>
  );
}
