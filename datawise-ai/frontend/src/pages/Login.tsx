import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import { ApiError } from "../api";
import { ErrorBox } from "../components/Feedback";

export function LoginPage() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("demo@acme.example");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the API");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm" aria-labelledby="login-title">
        <div>
          <h1 id="login-title" className="text-xl font-bold text-teal-700">DATAWISE AI</h1>
          <p className="text-sm text-slate-500">Ask business questions in plain language. SQL is generated, validated and run read-only.</p>
        </div>
        <label className="block text-sm">
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username"
            className="focus-ring mt-1 w-full rounded border border-slate-300 px-3 py-2" />
        </label>
        <label className="block text-sm">
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password"
            className="focus-ring mt-1 w-full rounded border border-slate-300 px-3 py-2" />
        </label>
        {error ? <ErrorBox message={error} /> : null}
        <button type="submit" disabled={busy}
          className="focus-ring w-full rounded bg-teal-700 px-3 py-2 font-medium text-white hover:bg-teal-800 disabled:opacity-50">
          {busy ? "Signing in" : "Sign in"}
        </button>
        <p className="text-xs text-slate-500">Demo users: demo@acme.example, demo@globex.example. Password = DEMO_USER_PASSWORD from your .env.</p>
      </form>
    </main>
  );
}
