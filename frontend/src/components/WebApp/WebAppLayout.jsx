import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

const WebAppLayout = () => {
  return (
    <div className="min-h-screen bg-[#020817] text-white">
      <Sidebar />

      <div className="ml-64">
        <Topbar />

        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default WebAppLayout;