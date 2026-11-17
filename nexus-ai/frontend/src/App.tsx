import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./components/auth";
import { Layout } from "./components/Layout";
import { Loading } from "./components/ui";
import { Admin } from "./pages/Admin";
import { Approvals } from "./pages/Approvals";
import { Chat } from "./pages/Chat";
import { Documents } from "./pages/Documents";
import { Investigations } from "./pages/Investigations";
import { Login } from "./pages/Login";
import { RunDetail } from "./pages/RunDetail";

export function App() {
  const { me, loading } = useAuth();
  if (loading) return <Loading label="Restoring session" />;
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {me ? (
        <Route element={<Layout />}>
          <Route path="/chat" element={<Chat />} />
          <Route path="/investigations" element={<Investigations />} />
          <Route path="/investigations/:id" element={<RunDetail />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Route>
      ) : (
        <Route path="*" element={<Navigate to="/login" replace />} />
      )}
    </Routes>
  );
}
