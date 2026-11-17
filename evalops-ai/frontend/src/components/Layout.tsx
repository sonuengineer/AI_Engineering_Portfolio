import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:bg-white focus:p-2">
        Skip to content
      </a>
      <header className="border-b border-slate-200 bg-white">
        <nav aria-label="Main" className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
          <Link to="/" className="font-bold tracking-tight text-slate-900">
            EVALOPS AI
          </Link>
          <NavLink
            to="/"
            end
            className={({ isActive }) => `text-sm ${isActive ? "font-semibold text-blue-800" : "text-slate-700 hover:text-slate-900"}`}
          >
            Projects
          </NavLink>
          <div className="ml-auto flex items-center gap-3 text-sm">
            {user && (
              <span className="text-slate-700">
                <span className="hidden sm:inline">{user.email} </span>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-800">{user.role}</span>
              </span>
            )}
            <button
              type="button"
              onClick={logout}
              className="rounded border border-slate-300 px-2 py-1 text-slate-800 hover:bg-slate-100"
            >
              Log out
            </button>
          </div>
        </nav>
      </header>
      <main id="main" className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

export function PageTitle({ children, sub }: { children: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="mb-4">
      <h1 className="break-words text-2xl font-semibold text-slate-900">{children}</h1>
      {sub && <div className="mt-1 text-sm text-slate-600">{sub}</div>}
    </div>
  );
}

export const btn =
  "inline-flex items-center justify-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50";
export const btnPrimary =
  "inline-flex items-center justify-center rounded-md bg-blue-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50";
export const input =
  "w-full rounded-md border border-slate-400 bg-white px-2 py-1.5 text-sm text-slate-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-200";
export const link = "text-blue-800 underline-offset-2 hover:underline";
