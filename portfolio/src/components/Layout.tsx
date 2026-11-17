import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { site } from "../config";

const nav = [
  { to: "/", label: "Home", end: true },
  { to: "/projects/nexus-ai", label: "NEXUS" },
  { to: "/projects/datawise-ai", label: "DATAWISE" },
  { to: "/projects/evalops-ai", label: "EVALOPS" },
  { to: "/interview", label: "Interview prep" },
];

export function Layout() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); document.getElementById("main")?.focus(); }, [pathname]);
  return (
    <div className="min-h-screen bg-slate-950">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:text-slate-900">Skip to content</a>
      <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <NavLink to="/" className="font-semibold tracking-tight text-white">{site.ownerName}<span className="text-indigo-400"> / AI Engineer</span></NavLink>
          <nav aria-label="Main" className="flex flex-wrap gap-1 text-sm">
            {nav.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end}
                className={({ isActive }) => `rounded-md px-3 py-1.5 ${isActive ? "bg-slate-800 text-white" : "text-slate-300 hover:bg-slate-900 hover:text-white"}`}>
                {n.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto max-w-6xl px-4 py-10 outline-none"><Outlet /></main>
      <footer className="border-t border-slate-800 py-8 text-center text-xs text-slate-500">
        Built as three independent repositories plus this site. All metrics shown come from committed benchmark artifacts; placeholders are labeled.
      </footer>
    </div>
  );
}
