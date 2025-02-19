import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Search,
  BookOpen,
  Network,
  Settings,
  Zap,
} from "lucide-react";
import clsx from "clsx";

const NAV_ITEMS = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/search", icon: Search, label: "Search" },
];

export default function Sidebar() {
  return (
    <aside className="w-60 flex flex-col bg-gray-900 border-r border-gray-800 shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-4 border-b border-gray-800">
        <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
          <Zap size={16} className="text-white" />
        </div>
        <div>
          <p className="font-bold text-sm text-white leading-tight">OmniRAG</p>
          <p className="text-xs text-gray-500">Knowledge Engine</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-600/20 text-brand-400"
                  : "text-gray-400 hover:text-gray-100 hover:bg-gray-800"
              )
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-gray-800">
        <p className="text-xs text-gray-600 text-center">OmniRAG v1.0.0</p>
      </div>
    </aside>
  );
}
