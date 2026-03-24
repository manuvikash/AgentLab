import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

const links = [
  { to: "/", label: "Dashboard", icon: "◆" },
  { to: "/playground", label: "Playground", icon: "💬" },
  { to: "/agents", label: "Agents", icon: "⚙" },
  { to: "/skills", label: "Skills", icon: "📋" },
  { to: "/runs", label: "Runs", icon: "▶" },
  { to: "/experiments", label: "Experiments", icon: "⬡" },
  { to: "/components", label: "Components", icon: "◫" },
  { to: "/tasks", label: "Tasks", icon: "☰" },
  { to: "/compare", label: "Compare", icon: "⇄" },
];

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-56 bg-gray-900 text-gray-300 flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-gray-800">
          <h1 className="text-lg font-bold text-white tracking-wide">AgentLab</h1>
          <p className="text-xs text-gray-500 mt-0.5">Research OS for AI Agents</p>
        </div>
        <nav className="flex-1 py-3 space-y-0.5 overflow-y-auto">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
                  isActive
                    ? "bg-indigo-600/20 text-indigo-400 border-r-2 border-indigo-400"
                    : "hover:bg-gray-800 hover:text-white"
                }`
              }
            >
              <span className="text-base">{l.icon}</span>
              {l.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-y-auto bg-gray-50 p-6">{children}</main>
    </div>
  );
}
