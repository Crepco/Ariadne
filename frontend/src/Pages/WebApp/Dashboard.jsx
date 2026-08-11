import React from "react";
const recentRuns = [
  {
    id: "RUN-012",
    environment: "Corporate AD v2",
    model: "Gemini Flash",
    status: "SUCCESS",
    score: "84%",
    time: "11 May 2026, 7:45 PM",
  },
  {
    id: "RUN-011",
    environment: "Corp AD - Small",
    model: "Gemini Flash",
    status: "SUCCESS",
    score: "78%",
    time: "11 May 2026, 5:12 PM",
  },
  {
    id: "RUN-010",
    environment: "Enterprise AD",
    model: "Gemini Flash",
    status: "FAILED",
    score: "42%",
    time: "11 May 2026, 2:33 PM",
  },
  {
    id: "RUN-009",
    environment: "Lab AD",
    model: "Gemini Flash",
    status: "SUCCESS",
    score: "88%",
    time: "10 May 2026, 11:02 PM",
  },
  {
    id: "RUN-008",
    environment: "Corporate AD v1",
    model: "Gemini Flash",
    status: "SUCCESS",
    score: "73%",
    time: "10 May 2026, 6:18 PM",
  },
];

const navItems = [
  { label: "Dashboard", icon: "⌂", active: true },
  { label: "New Benchmark", icon: "✦" },
  { label: "Environments", icon: "◉" },
  { label: "Runs", icon: "↻" },
  { label: "Results", icon: "◇" },
  { label: "Reports", icon: "▣" },
];

const StatCard = ({ title, value, subtitle, icon }) => (
  <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 shadow-lg">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs font-medium text-slate-400">{title}</p>
        <h3 className="mt-2 text-3xl font-semibold text-white">{value}</h3>
        <p className="mt-2 text-xs text-slate-500">{subtitle}</p>
      </div>

      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-500/10 text-lg text-violet-400">
        {icon}
      </div>
    </div>
  </div>
);

const StatusBadge = ({ status }) => {
  const success = status === "SUCCESS";

  return (
    <span
      className={`rounded-md px-2 py-1 text-[10px] font-semibold tracking-wide ${
        success
          ? "bg-emerald-500/15 text-emerald-400"
          : "bg-red-500/15 text-red-400"
      }`}
    >
      {status}
    </span>
  );
};

const Dashboard = () => {
  return (
    <div className="min-h-screen bg-[#070b13] text-white">
      <div className="flex min-h-screen">




        {/* MAIN AREA */}
        <main className="flex min-w-0 flex-1 flex-col">


          {/* DASHBOARD CONTENT */}
          <section className="flex-1 overflow-y-auto px-5 py-7 md:px-8">

            {/* Heading */}
            <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <p className="mb-1 text-sm text-violet-400">
                  Ariadne Web App
                </p>

                <h2 className="text-2xl font-semibold tracking-tight text-white md:text-3xl">
                  Dashboard
                </h2>

                <p className="mt-1 text-sm text-slate-500">
                  Monitor your AI agent evaluations and benchmark performance.
                </p>
              </div>

              <button className="rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-medium text-white shadow-lg shadow-violet-600/20 transition hover:bg-violet-500">
                + New Benchmark Run
              </button>
            </div>

            {/* STAT CARDS */}
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

              <StatCard
                title="Total Runs"
                value="12"
                subtitle="+2 this week"
                icon="▦"
              />

              <StatCard
                title="Success Rate"
                value="75%"
                subtitle="+8% this week"
                icon="↗"
              />

              <StatCard
                title="Average Score"
                value="81%"
                subtitle="+6% this week"
                icon="⌁"
              />

              <StatCard
                title="Environments"
                value="5"
                subtitle="Active"
                icon="◈"
              />

            </div>

            {/* LOWER GRID */}
            <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_320px]">

              {/* RECENT RUNS */}
              <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60">

                <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
                  <div>
                    <h3 className="text-sm font-semibold text-white">
                      Recent Runs
                    </h3>

                    <p className="mt-1 text-xs text-slate-500">
                      Latest benchmark evaluations
                    </p>
                  </div>

                  <button className="text-xs text-violet-400 hover:text-violet-300">
                    View All Runs →
                  </button>
                </div>

                {/* Desktop table */}
                <div className="hidden overflow-x-auto md:block">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-600">
                        <th className="px-5 py-3 font-medium">Run ID</th>
                        <th className="px-3 py-3 font-medium">Environment</th>
                        <th className="px-3 py-3 font-medium">Model</th>
                        <th className="px-3 py-3 font-medium">Status</th>
                        <th className="px-3 py-3 font-medium">Score</th>
                        <th className="px-3 py-3 font-medium">Started At</th>
                      </tr>
                    </thead>

                    <tbody>
                      {recentRuns.map((run) => (
                        <tr
                          key={run.id}
                          className="border-b border-slate-800/70 transition hover:bg-slate-800/30"
                        >
                          <td className="px-5 py-4 text-xs font-medium text-slate-300">
                            {run.id}
                          </td>

                          <td className="px-3 py-4 text-xs text-slate-400">
                            {run.environment}
                          </td>

                          <td className="px-3 py-4 text-xs text-slate-400">
                            {run.model}
                          </td>

                          <td className="px-3 py-4">
                            <StatusBadge status={run.status} />
                          </td>

                          <td className="px-3 py-4 text-xs font-semibold text-white">
                            {run.score}
                          </td>

                          <td className="px-3 py-4 text-[11px] text-slate-500">
                            {run.time}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile */}
                <div className="space-y-2 p-4 md:hidden">
                  {recentRuns.map((run) => (
                    <div
                      key={run.id}
                      className="rounded-lg border border-slate-800 bg-slate-950/40 p-4"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-white">
                          {run.id}
                        </span>

                        <StatusBadge status={run.status} />
                      </div>

                      <div className="mt-3 flex justify-between text-xs">
                        <span className="text-slate-500">
                          {run.environment}
                        </span>

                        <span className="font-semibold text-white">
                          {run.score}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* RIGHT COLUMN */}
              <div className="space-y-5">

                {/* QUICK START */}
                <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">

                  <h3 className="text-sm font-semibold text-white">
                    Quick Start
                  </h3>

                  <p className="mt-1 text-xs text-slate-500">
                    Start working with Ariadne
                  </p>

                  <div className="mt-5 space-y-2">

                    <button className="flex w-full items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-left transition hover:border-violet-500/40 hover:bg-violet-500/5">
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/10 text-violet-400">
                        +
                      </span>

                      <div>
                        <p className="text-xs font-medium text-white">
                          New Benchmark
                        </p>
                        <p className="text-[10px] text-slate-500">
                          Start a new evaluation
                        </p>
                      </div>
                    </button>

                    <button className="flex w-full items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-left transition hover:border-cyan-500/40 hover:bg-cyan-500/5">
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400">
                        ↑
                      </span>

                      <div>
                        <p className="text-xs font-medium text-white">
                          Upload BloodHound ZIP
                        </p>
                        <p className="text-[10px] text-slate-500">
                          Use your own AD data
                        </p>
                      </div>
                    </button>

                    <button className="flex w-full items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-left transition hover:border-emerald-500/40 hover:bg-emerald-500/5">
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
                        ◈
                      </span>

                      <div>
                        <p className="text-xs font-medium text-white">
                          Browse Environments
                        </p>
                        <p className="text-[10px] text-slate-500">
                          View available environments
                        </p>
                      </div>
                    </button>

                  </div>
                </div>

                {/* SYSTEM STATUS */}
                <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">

                  <h3 className="text-sm font-semibold text-white">
                    System Status
                  </h3>

                  <div className="mt-4 space-y-3">

                    {[
                      "Backend API",
                      "Neo4j Database",
                      "LLM Service",
                    ].map((service) => (
                      <div
                        key={service}
                        className="flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50" />

                          <span className="text-xs text-slate-400">
                            {service}
                          </span>
                        </div>

                        <span className="text-[10px] font-medium text-emerald-400">
                          Online
                        </span>
                      </div>
                    ))}

                  </div>
                </div>

              </div>
            </div>

            {/* BOTTOM INFO */}
            <div className="mt-5 rounded-xl border border-violet-500/10 bg-violet-500/[0.03] p-5">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">

                <div>
                  <p className="text-sm font-medium text-white">
                    Ready to evaluate an AI agent?
                  </p>

                  <p className="mt-1 text-xs text-slate-500">
                    Configure an environment and start your first Ariadne benchmark.
                  </p>
                </div>

                <button className="w-fit rounded-lg border border-violet-500/30 px-4 py-2 text-xs font-medium text-violet-300 transition hover:bg-violet-500/10">
                  Start Benchmark →
                </button>

              </div>
            </div>

          </section>
        </main>
      </div>

    </div>
  );
};

export default Dashboard;