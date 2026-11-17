import { NavLink, Outlet } from "react-router-dom";
import { hasRole, useAuth } from "./auth";
import { Button, ProviderBadge, cx } from "./ui";

const NAV = [
  { to: "/chat", label: "Ask", role: "viewer" },
  { to: "/investigations", label: "Investigations", role: "viewer" },
  { to: "/approvals", label: "Approvals", role: "viewer" },
  { to: "/documents", label: "Documents", role: "viewer" },
  { to: "/admin", label: "Admin", role: "manager" },
];

export function Layout() {
  const { me, logout } = useAuth();
  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">Skip to content</a>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="text-lg font-bold tracking-tight text-brand-900">NEXUS<span className="text-brand-600"> AI</span></span>
          <nav aria-label="Primary" className="flex flex-wrap gap-1">
            {NAV.filter((n) => hasRole(me, n.role)).map((n) => (
              <NavLink key={n.to} to={n.to} className={({ isActive }) => cx("rounded-md px-3 py-1.5 text-sm font-medium", isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100")}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            {me && <ProviderBadge provider={me.llm_provider} />}
            <span className="hidden text-slate-600 sm:inline">{me?.full_name} <span className="text-slate-400">({me?.role}, {me?.org_name})</span></span>
            <Button variant="ghost" onClick={logout}>Sign out</Button>
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-7xl px-4 py-6"><Outlet /></main>
    </div>
  );
}
