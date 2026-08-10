import { BrowserRouter, Routes, Route } from "react-router-dom";

import LandingPage from "./Pages/LandingPage";
import Demo from "./Pages/Demo";
import BenchmarkPage from "./Pages/BenchmarkPage";
import Navbar from "./components/LandingPage/Navbar";

const App = () => {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#020817] text-white">
        <Navbar />

        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/demo" element={<Demo />} />
          <Route path="/benchmark" element={<BenchmarkPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
};

export default App;