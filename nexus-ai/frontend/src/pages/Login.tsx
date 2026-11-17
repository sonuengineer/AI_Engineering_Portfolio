import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../components/auth";
import { Button, ErrorBanner } from "../components/ui";

const DEMO = ["manager@acme.example", "analyst@acme.example", "viewer@acme.example", "admin@acme.example", "admin@globex.example"];

export function Login() {
  const { me, login } = useAuth();
  const [email, setEmail] = useState(DEMO[0]!);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  if (me) return <Navigate to="/chat" replace />;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(undefined);
    try { await login(email, password); } catch (err) { setError(err); } finally { setBusy(false); }
  };
  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm" aria-labelledby="login-title">
        <div>
          <h1 id="login-title" className="text-xl font-bold text-brand-900">NEXUS AI</h1>
          <p className="text-sm text-slate-500">Enterprise intelligence with grounded answers and human-approved actions.</p>
        </div>
        <ErrorBanner error={error} />
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-slate-700">Email</label>
          <input id="email" type="email" list="demo-users" required value={email} onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" autoComplete="username" />
          <datalist id="demo-users">{DEMO.map((d) => <option key={d} value={d} />)}</datalist>
        </div>
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-slate-700">Password</label>
          <input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" autoComplete="current-password" />
          <p className="mt-1 text-xs text-slate-500">Demo users share the password set in <code>DEMO_USER_PASSWORD</code> (see .env).</p>
        </div>
        <Button type="submit" busy={busy} className="w-full">Sign in</Button>
      </form>
    </main>
  );
}
