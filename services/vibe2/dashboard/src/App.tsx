import { Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login.tsx";
import Briefing from "./pages/Briefing.tsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Briefing />} />
      <Route path="/login" element={<Login />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
