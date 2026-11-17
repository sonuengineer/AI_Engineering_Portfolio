import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { RequireAuth } from "./auth/RequireAuth";
import { Loading } from "./components/DataState";
import { Layout, PageTitle, link } from "./components/Layout";
import { ComparePage } from "./pages/ComparePage";
import { DatasetCasesPage } from "./pages/DatasetCasesPage";
import { LoginPage } from "./pages/LoginPage";
import { NewRunPage } from "./pages/NewRunPage";
import { ProjectPage } from "./pages/ProjectPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { TracePage } from "./pages/TracePage";

// Run detail pulls in recharts; load it on demand to keep the initial bundle small.
const RunDetailPage = lazy(() => import("./pages/RunDetailPage").then((m) => ({ default: m.RunDetailPage })));

function NotFound() {
  return (
    <>
      <PageTitle>Page not found</PageTitle>
      <Link to="/" className={link}>
        Go to projects
      </Link>
    </>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={<ProjectsPage />} />
          <Route path="projects/:projectId" element={<ProjectPage />} />
          <Route path="projects/:projectId/runs/new" element={<NewRunPage />} />
          <Route path="projects/:projectId/dataset-versions/:versionId" element={<DatasetCasesPage />} />
          <Route
            path="runs/:runId"
            element={
              <Suspense fallback={<Loading label="Loading run view" />}>
                <RunDetailPage />
              </Suspense>
            }
          />
          <Route path="compare" element={<ComparePage />} />
          <Route path="traces/:traceId" element={<TracePage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  );
}
