import { BrowserRouter, Routes, Route } from "react-router-dom";

import LandingPage from "./Pages/LandingPage";
import Demo from "./Pages/Demo";
import BenchmarkPage from "./Pages/BenchmarkPage";

import Navbar from "./components/LandingPage/Navbar";
import WebAppLayout from "./components/WebApp/WebAppLayout";

import Dashboard from "./Pages/WebApp/Dashboard";

const App = () => {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#020817] text-white">

        <Routes>

          <Route path="/" element={<><Navbar /><LandingPage /></>} />

          <Route path="/demo" element={<><Navbar /><Demo /></>} />

          <Route path="/benchmark" element={<><Navbar /><BenchmarkPage /></>} />

          <Route path="/app" element={<WebAppLayout />}>
            <Route index element={<Dashboard />} />
          </Route>

        </Routes>

      </div>
    </BrowserRouter>
  );
};

export default App;