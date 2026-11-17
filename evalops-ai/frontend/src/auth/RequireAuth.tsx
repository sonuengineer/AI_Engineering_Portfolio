import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { Loading } from "../components/DataState";

export function RequireAuth() {
  const { token, user, loading } = useAuth();
  const location = useLocation();
  if (!token) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (loading || !user) return <Loading label="Checking session" />;
  return <Outlet />;
}
