import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout.jsx";
import { AuthProvider, useAuth } from "./context/AuthContext.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import LeadAnalyticsPage from "./pages/LeadAnalyticsPage.jsx";
import LeadDetailPage from "./pages/LeadDetailPage.jsx";
import LearnerDetailPage from "./pages/LearnerDetailPage.jsx";
import LearnersPage from "./pages/LearnersPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import OpportunitiesPage from "./pages/OpportunitiesPage.jsx";
import UploadsPage from "./pages/UploadsPage.jsx";
import CampaignsPage from "./pages/CampaignsPage.jsx";
import MainCrmPage from "./pages/MainCrmPage.jsx";
import MainCrmOverviewPage from "./pages/MainCrmOverviewPage.jsx";
import MainCrmAnalyticsPage from "./pages/MainCrmAnalyticsPage.jsx";
import MainCrmUploadsPage from "./pages/MainCrmUploadsPage.jsx";
import MainCrmCampaignsPage from "./pages/MainCrmCampaignsPage.jsx";
import CounselorMappingPage from "./pages/CounselorMappingPage.jsx";
import MainCrmLeadDetailPage from "./pages/MainCrmLeadDetailPage.jsx";
import LearnersCrmOverviewPage from "./pages/LearnersCrmOverviewPage.jsx";
import LearnersCrmUploadsPage from "./pages/LearnersCrmUploadsPage.jsx";

function RequireAuth() {
  const { user, loading } = useAuth();
  if (loading) return <div className="page">Loading CRM...</div>;
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}

function RequireAdmin() {
  const { user } = useAuth();
  return user?.role === "ADMIN" ? <Outlet /> : <Navigate to="/upsell" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAuth />}>
            <Route element={<AppLayout />}>
              <Route path="/crm" element={<MainCrmOverviewPage />} />
              <Route path="/crm/leads" element={<MainCrmPage />} />
              <Route path="/crm/leads/:leadId" element={<MainCrmLeadDetailPage />} />
              <Route path="/crm/analytics" element={<MainCrmAnalyticsPage />} />
              <Route path="/crm/campaigns" element={<MainCrmCampaignsPage />} />
              <Route element={<RequireAdmin />}>
                <Route path="/crm/uploads" element={<MainCrmUploadsPage />} />
                <Route path="/crm/mapping" element={<CounselorMappingPage />} />
              </Route>
              <Route path="/upsell" element={<DashboardPage />} />
              <Route path="/upsell/opportunities" element={<OpportunitiesPage />} />
              <Route path="/upsell/opportunities/idp" element={<OpportunitiesPage />} />
              <Route path="/upsell/leads/:leadId" element={<LeadDetailPage />} />
              <Route path="/upsell/lead-analytics" element={<LeadAnalyticsPage />} />
              <Route path="/upsell/campaigns" element={<CampaignsPage />} />
              <Route path="/upsell/learners/:learnerNumber" element={<LearnerDetailPage />} />
              <Route element={<RequireAdmin />}>
                <Route path="/upsell/learners" element={<LearnersPage />} />
                <Route path="/upsell/uploads" element={<UploadsPage />} />
              </Route>
              <Route path="/learners-crm" element={<LearnersCrmOverviewPage />} />
              <Route element={<RequireAdmin />}>
                <Route path="/learners-crm/uploads" element={<LearnersCrmUploadsPage />} />
              </Route>
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/crm" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
