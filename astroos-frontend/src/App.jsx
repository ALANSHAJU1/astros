import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "./context/AuthContext";
import AppLayout from "./components/AppLayout";
import LoadingScreen from "./components/LoadingScreen";
import ProtectedRoute from "./components/ProtectedRoute";
import Admin from "./pages/Admin";
import Dashboard from "./pages/Dashboard";
import Explore from "./pages/Explore";
import Login from "./pages/Login";
import Planner from "./pages/Planner";
import Profile from "./pages/Profile";
import Recommendations from "./pages/Recommendations";
import Register from "./pages/Register";
import Visibility from "./pages/Visibility";

function AppRoutes() {
  const { ready } = useAuth();

  if (!ready) {
    return <LoadingScreen />;
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/explore" element={<Explore />} />
        <Route path="/planner" element={<Planner />} />
        <Route path="/visibility" element={<Visibility />} />
        <Route path="/recommendations" element={<Recommendations />} />
        <Route path="/profile" element={<Profile />} />
        <Route
          path="/admin"
          element={
            <ProtectedRoute adminOnly>
              <Admin />
            </ProtectedRoute>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
