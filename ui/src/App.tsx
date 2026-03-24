import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import AgentsList from "./pages/AgentsList";
import AgentDetail from "./pages/AgentDetail";
import AgentBuilder from "./pages/AgentBuilder";
import RunsList from "./pages/RunsList";
import RunDetail from "./pages/RunDetail";
import ExperimentsList from "./pages/ExperimentsList";
import ExperimentDetail from "./pages/ExperimentDetail";
import ExperimentBuilder from "./pages/ExperimentBuilder";
import ComponentsList from "./pages/ComponentsList";
import TasksList from "./pages/TasksList";
import TaskDetail from "./pages/TaskDetail";
import TaskBuilder from "./pages/TaskBuilder";
import SkillsList from "./pages/SkillsList";
import SkillDetail from "./pages/SkillDetail";
import SkillBuilder from "./pages/SkillBuilder";
import Compare from "./pages/Compare";
import Playground from "./pages/Playground";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/agents" element={<AgentsList />} />
        <Route path="/agents/new" element={<AgentBuilder />} />
        <Route path="/agents/:name" element={<AgentDetail />} />
        <Route path="/agents/:name/edit" element={<AgentBuilder />} />
        <Route path="/runs" element={<RunsList />} />
        <Route path="/runs/:id" element={<RunDetail />} />
        <Route path="/experiments" element={<ExperimentsList />} />
        <Route path="/experiments/new" element={<ExperimentBuilder />} />
        <Route path="/experiments/:id" element={<ExperimentDetail />} />
        <Route path="/components" element={<ComponentsList />} />
        <Route path="/tasks" element={<TasksList />} />
        <Route path="/tasks/new" element={<TaskBuilder />} />
        <Route path="/tasks/:id" element={<TaskDetail />} />
        <Route path="/tasks/:id/edit" element={<TaskBuilder />} />
        <Route path="/skills" element={<SkillsList />} />
        <Route path="/skills/new" element={<SkillBuilder />} />
        <Route path="/skills/:id" element={<SkillDetail />} />
        <Route path="/skills/:id/edit" element={<SkillBuilder />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/playground" element={<Playground />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
