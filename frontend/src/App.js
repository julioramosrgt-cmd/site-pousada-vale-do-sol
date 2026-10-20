import "@/App.css";
import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/lib/auth";
import { ColabAuthProvider } from "@/lib/colabAuth";
import PublicSite from "@/pages/PublicSite";
import PublicReservation from "@/pages/PublicReservation";
import AdminLogin from "@/pages/AdminLogin";
import AdminLayout from "@/pages/admin/AdminLayout";
import Dashboard from "@/pages/admin/Dashboard";
import CalendarPage from "@/pages/admin/CalendarPage";
import ReservationsPage from "@/pages/admin/ReservationsPage";
import RoomsPage from "@/pages/admin/RoomsPage";
import SettingsPage from "@/pages/admin/SettingsPage";
import ICalPage from "@/pages/admin/ICalPage";
import WhatsAppPage from "@/pages/admin/WhatsAppPage";
import FinancePage from "@/pages/admin/FinancePage";
import AccountPage from "@/pages/admin/AccountPage";
import UsersPage from "@/pages/admin/UsersPage";
import HeatmapPage from "@/pages/admin/HeatmapPage";
import RhLogin from "@/pages/rh/RhLogin";
import RhLayout from "@/pages/rh/RhLayout";
import RhDashboard from "@/pages/rh/RhDashboard";
import EmployeesPage from "@/pages/rh/EmployeesPage";
import SchedulePage from "@/pages/rh/SchedulePage";
import ColabLogin from "@/pages/colaborador/ColabLogin";
import ColabLayout from "@/pages/colaborador/ColabLayout";
import ColabDashboard from "@/pages/colaborador/ColabDashboard";
import ColabPonto from "@/pages/colaborador/ColabPonto";
import ColabFerias from "@/pages/colaborador/ColabFerias";
import PontoPage from "@/pages/rh/PontoPage";
import FeriasPage from "@/pages/rh/FeriasPage";
import FolhaPage from "@/pages/rh/FolhaPage";

// --- Redirect do admin antigo para o novo painel externo ---
// Painel admin migrou para https://admin.pousadavaledosol2024.com.br/.
// Para reverter: remova o componente abaixo e descomente as rotas /admin.
const NEW_ADMIN_URL = "https://admin.pousadavaledosol2024.com.br/";
function RedirectToNewAdmin() {
  useEffect(() => { window.location.replace(NEW_ADMIN_URL); }, []);
  return (
    <div className="min-h-screen flex items-center justify-center text-stone-600 text-sm" data-testid="admin-redirect">
      Redirecionando para o novo painel administrativo…
    </div>
  );
}

function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-10 text-stone-500">Carregando...</div>;
  if (!user) return <Navigate to="/admin/login" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <ColabAuthProvider>
        <BrowserRouter>
          <Toaster position="top-right" richColors />
          <Routes>
            <Route path="/" element={<PublicSite />} />
            <Route path="/reservar" element={<PublicReservation />} />

            {/* Redirect antigo /admin/* -> novo painel externo (reversível) */}
            <Route path="/admin/*" element={<RedirectToNewAdmin />} />

            {/* ===== Módulo RH (gestor) ===== */}
            <Route path="/rh/login" element={<RhLogin />} />
            <Route path="/rh" element={<RhLayout />}>
              <Route index element={<RhDashboard />} />
              <Route path="colaboradores" element={<EmployeesPage />} />
              <Route path="escala" element={<SchedulePage />} />
              <Route path="ponto" element={<PontoPage />} />
              <Route path="ferias" element={<FeriasPage />} />
              <Route path="folha" element={<FolhaPage />} />
            </Route>

            {/* ===== Portal do Colaborador ===== */}
            <Route path="/colaborador/login" element={<ColabLogin />} />
            <Route path="/colaborador" element={<ColabLayout />}>
              <Route index element={<ColabDashboard />} />
              <Route path="ponto" element={<ColabPonto />} />
              <Route path="ferias" element={<ColabFerias />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ColabAuthProvider>
    </AuthProvider>
  );
}
