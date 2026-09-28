import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/lib/auth";
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

function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-10 text-stone-500">Carregando...</div>;
  if (!user) return <Navigate to="/admin/login" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" richColors />
        <Routes>
          <Route path="/" element={<PublicSite />} />
          <Route path="/reservar" element={<PublicReservation />} />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/admin" element={<RequireAuth><AdminLayout /></RequireAuth>}>
            <Route index element={<Dashboard />} />
            <Route path="calendar" element={<CalendarPage />} />
            <Route path="reservations" element={<ReservationsPage />} />
            <Route path="rooms" element={<RoomsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="ical" element={<ICalPage />} />
            <Route path="whatsapp" element={<WhatsAppPage />} />
            <Route path="finance" element={<FinancePage />} />
            <Route path="account" element={<AccountPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
