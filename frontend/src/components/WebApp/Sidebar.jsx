import { NavLink } from "react-router-dom";
import {
  LuLayoutDashboard,
  LuPlus,
  LuServer,
  LuActivity,
  LuChartColumn,
  LuFileText,
  LuSettings,
} from "react-icons/lu";

const LINKS = [
  { name: "Dashboard", path: "/app", icon: LuLayoutDashboard, end: true },
  { name: "New benchmark", path: "/app/benchmark", icon: LuPlus },
  { name: "Environments", path: "/app/environments", icon: LuServer },
  { name: "Runs", path: "/app/runs", icon: LuActivity },
  { name: "Results", path: "/app/results", icon: LuChartColumn },
  { name: "Reports", path: "/app/reports", icon: LuFileText },
];

const linkClasses = ({ isActive }) =>
  `group relative flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm transition-colors duration-200 ${
    isActive
      ? "bg-[#7C5CFF]/10 text-white"
      : "text-[#8E9AB3] hover:bg-[#0B1224] hover:text-[#E5E7F0]"
  }`;

const Sidebar = () => {
  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-[#020817] border-r border-[#172B52] z-50 flex flex-col">

      {/* Brand */}
      <div className="h-16 px-5 flex items-center gap-3 border-b border-[#172B52]">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#7C5CFF] to-[#9B7BFF] flex items-center justify-center shrink-0">
          <span className="text-white text-sm font-bold">A</span>
        </div>
        <div className="leading-none">
          <h1 className="text-[15px] font-bold text-white tracking-wide">
            ARIADNE
          </h1>
          <p className="mt-1 text-[10px] tracking-widest text-[#596783]">
            AI SECURITY BENCHMARK
          </p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-5 overflow-y-auto">
        <p className="px-3.5 mb-2 text-[10px] font-medium tracking-widest text-[#4A4F73] uppercase">
          Workspace
        </p>

        <div className="space-y-0.5">
          {LINKS.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink
                key={link.path}
                to={link.path}
                end={link.end}
                className={linkClasses}
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={`absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[2px] rounded-full bg-[#7C5CFF] transition-opacity duration-200 ${
                        isActive ? "opacity-100" : "opacity-0"
                      }`}
                    />
                    <Icon
                      size={17}
                      className={
                        isActive
                          ? "text-[#A78BFA]"
                          : "text-[#596783] group-hover:text-[#9B83E2] transition-colors duration-200"
                      }
                    />
                    <span>{link.name}</span>
                  </>
                )}
              </NavLink>
            );
          })}
        </div>
      </nav>

      {/* Settings */}
      <div className="p-3 border-t border-[#172B52]">
        <NavLink to="/app/settings" className={linkClasses}>
          {({ isActive }) => (
            <>
              <span
                className={`absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[2px] rounded-full bg-[#7C5CFF] transition-opacity duration-200 ${
                  isActive ? "opacity-100" : "opacity-0"
                }`}
              />
              <LuSettings
                size={17}
                className={
                  isActive
                    ? "text-[#A78BFA]"
                    : "text-[#596783] group-hover:text-[#9B83E2] transition-colors duration-200"
                }
              />
              <span>Settings</span>
            </>
          )}
        </NavLink>
      </div>

    </aside>
  );
};

export default Sidebar;