import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";

const LINKS = [
  { to: "/", label: "Ask" },
  { to: "/history", label: "History" },
  { to: "/reports", label: "Saved reports" },
  { to: "/catalog", label: "Catalog" },
];

export function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="text-lg font-bold text-teal-700">DATAWISE AI</span>
          <nav aria-label="Main" className="flex flex-wrap gap-1">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end
                className={({ isActive }) =>
                  `focus-ring rounded px-3 py-1.5 text-sm ${isActive ? "bg-teal-50 font-medium text-teal-800" : "text-slate-600 hover:bg-slate-100"}`}>
                {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm text-slate-600">
            <span className="hidden sm:inline">{user?.full_name} -- {user?.org_name}</span>
            <button type="button" onClick={logout} className="focus-ring rounded border border-slate-300 px-2 py-1 hover:bg-slate-100">
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
