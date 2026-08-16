import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AdminLayout } from "./components/AdminLayout";

import { DashboardPage } from "./pages/public/DashboardPage";
import { CommodityDetailPage } from "./pages/public/CommodityDetailPage";
import { PredictPage } from "./pages/public/PredictPage";
import { ExplorePage } from "./pages/public/ExplorePage";
import { EwsPage } from "./pages/public/EwsPage";
import { ProjectionPage } from "./pages/public/ProjectionPage";

import { LoginPage } from "./pages/admin/LoginPage";
import { AdminHomePage } from "./pages/admin/AdminHomePage";
import { PriceInputPage } from "./pages/admin/PriceInputPage";
import { PriceHistoryPage } from "./pages/admin/PriceHistoryPage";
import { ForecastMonitorPage } from "./pages/admin/ForecastMonitorPage";
import { ModelManagerPage } from "./pages/admin/ModelManagerPage";
import { EwsConfigPage } from "./pages/admin/EwsConfigPage";

export function App() {
  return (
    <Routes>
      <Route path="/admin/login" element={<LoginPage />} />

      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="komoditas/:code" element={<CommodityDetailPage />} />
        <Route path="prediksi" element={<PredictPage />} />
        <Route path="eksplorasi" element={<ExplorePage />} />
        <Route path="peringatan" element={<EwsPage />} />
        <Route path="proyeksi" element={<ProjectionPage />} />
      </Route>

      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<AdminHomePage />} />
        <Route path="input-harga" element={<PriceInputPage />} />
        <Route path="riwayat" element={<PriceHistoryPage />} />
        <Route path="forecast" element={<ForecastMonitorPage />} />
        <Route path="model" element={<ModelManagerPage />} />
        <Route path="ews" element={<EwsConfigPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
