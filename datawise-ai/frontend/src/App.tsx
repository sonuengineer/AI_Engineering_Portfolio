import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { Loading } from "./components/Feedback";
import { AskPage } from "./pages/Ask";
import { CatalogPage } from "./pages/Catalog";
import { HistoryPage } from "./pages/History";
import { LoginPage } from "./pages/Login";
import { ReportsPage } from "./pages/Reports";

function Protected() {
  const { user, loading } = useAuth();
  if (loading) return <Loading label="Checking session" />;
  if (!user) return <Navigate to="/login" replace />;
  return <Layout />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<Protected />}>
            <Route path="/" element={<AskPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/catalog" element={<CatalogPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
