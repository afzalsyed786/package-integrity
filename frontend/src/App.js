import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import Layout from "./components/pia/Layout";
import Overview from "./pages/Overview";
import Analyze from "./pages/Analyze";
import AnalysisDetail from "./pages/AnalysisDetail";
import Workspace from "./pages/Workspace";
import Watchlist from "./pages/Watchlist";
import History from "./pages/History";
import Alerts from "./pages/Alerts";
import Lab from "./pages/Lab";

function App() {
  return (
    <div className="dark">
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Overview />} />
            <Route path="analyze" element={<Analyze />} />
            <Route path="analyses/:id" element={<AnalysisDetail />} />
            <Route path="comparison" element={<Workspace tab="files" />} />
            <Route path="anomalies" element={<Workspace tab="findings" />} />
            <Route path="ai" element={<Workspace tab="ai" />} />
            <Route path="watchlist" element={<Watchlist />} />
            <Route path="history" element={<History />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="lab" element={<Lab />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster theme="dark" position="bottom-right" />
    </div>
  );
}

export default App;
