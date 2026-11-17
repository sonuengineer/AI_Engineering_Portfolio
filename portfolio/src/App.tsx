import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Home } from "./pages/Home";
import { InterviewHub } from "./pages/InterviewHub";
import { InterviewProject } from "./pages/InterviewProject";
import { NotFound } from "./pages/NotFound";
import { ProjectDetail } from "./pages/ProjectDetail";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="projects/:slug" element={<ProjectDetail />} />
        <Route path="interview" element={<InterviewHub />} />
        <Route path="interview/:project" element={<InterviewProject />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
