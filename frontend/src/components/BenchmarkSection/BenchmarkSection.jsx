import React from "react";
import {
  FaBullseye,
  FaRoute,
  FaBolt,
  FaXmark,
  FaChartLine,
} from "react-icons/fa6";

const METRICS = [
  {
    icon: <FaBullseye />,
    title: "Goal achievement",
    description: "Did the agent successfully reach the target privilege?",
  },
  {
    icon: <FaRoute />,
    title: "Path efficiency",
    description: "How efficiently did the agent navigate the attack graph?",
  },
  {
    icon: <FaBolt />,
    title: "Action efficiency",
    description: "How many actions were required to reach the objective?",
  },
  {
    icon: <FaXmark />,
    title: "Failure rate",
    description: "How often did the agent make ineffective decisions?",
  },
  {
    icon: <FaChartLine />,
    title: "Path quality",
    description: "Did the agent discover a valid and meaningful attack path?",
  },
];

const BenchmarkSection = () => {
  return (
    <section
      id="benchmark"
      className="relative overflow-hidden bg-[#020817] px-6 py-28 text-white"
    >
      {/* Background */}
      <div className="pointer-events-none absolute left-1/2 top-20 h-[500px] w-[700px] -translate-x-1/2 rounded-full bg-[#6946FF]/8 blur-[150px]" />

      <div className="relative mx-auto max-w-7xl">

        {/* Section heading */}
        <div className="mx-auto max-w-3xl text-center">
          <p className="mb-4 text-sm font-semibold uppercase tracking-[0.3em] text-[#7C5CFF]">
            The benchmark
          </p>

          <h2 className="text-4xl font-bold tracking-tight md:text-6xl">
            Measure how AI agents
            <span className="block bg-gradient-to-r from-[#7C5CFF] via-[#9B83E2] to-[#7D94F0] bg-clip-text text-transparent">
              navigate attack paths.
            </span>
          </h2>

          <p className="mt-6 text-base leading-8 text-[#8E9AB3] md:text-lg">
            Ariadne evaluates an AI agent inside a controlled Active Directory
            environment and measures how effectively it can reason through
            relationships, discover viable paths, and reach a target privilege.
          </p>
        </div>

        {/* Pipeline — one panel, three inline stages, not three cards */}
        <div className="mx-auto mt-20 max-w-4xl">
          <div className="rounded-2xl border border-[#172B52] bg-[#061027]/70 backdrop-blur-sm">
            <div className="grid divide-y divide-[#172B52] md:grid-cols-3 md:divide-y-0 md:divide-x">
              {[
                { icon: <FaBullseye />, label: "Objective", title: "Reach the goal", desc: "The agent receives a defined objective inside the AD environment." },
                { icon: <FaRoute />, label: "Agent", title: "Navigate the graph", desc: "The LLM explores relationships and chooses actions toward the objective." },
                { icon: <FaChartLine />, label: "Evaluation", title: "Measure performance", desc: "Every run is scored against measurable benchmark metrics." },
              ].map((stage) => (
                <div key={stage.label} className="p-7">
                  <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-lg bg-[#7C5CFF]/10 text-[#A78BFA]">
                    {stage.icon}
                  </div>
                  <p className="text-xs uppercase tracking-widest text-[#596783]">
                    {stage.label}
                  </p>
                  <h3 className="mt-2 text-lg font-semibold text-white">
                    {stage.title}
                  </h3>
                  <p className="mt-3 text-sm leading-6 text-[#8E9AB3]">
                    {stage.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Metrics — one panel, list rows instead of five cards */}
        <div className="mt-24">
          <div className="mb-10 text-center">
            <h3 className="text-2xl font-semibold md:text-3xl">
              What Ariadne measures
            </h3>
            <p className="mt-3 text-[#8E9AB3]">
              A benchmark should measure more than just success or failure.
            </p>
          </div>

          <div className="mx-auto max-w-5xl rounded-2xl border border-[#172B52] bg-[#061027]/70 backdrop-blur-sm">
            <div className="grid divide-y divide-[#172B52] sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-5 lg:divide-x">
              {METRICS.map((metric) => (
                <div
                  key={metric.title}
                  className="group p-6 transition-colors duration-300 hover:bg-[#08142E]"
                >
                  <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-lg bg-[#0B1833] text-[#A78BFA] transition-colors group-hover:bg-[#7C5CFF]/15 group-hover:text-white">
                    {metric.icon}
                  </div>
                  <h4 className="font-semibold text-white">{metric.title}</h4>
                  <p className="mt-2.5 text-sm leading-6 text-[#8996B1]">
                    {metric.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Example result — one panel, inline stat row instead of a 5-column grid of boxes */}
        <div className="mx-auto mt-24 max-w-5xl overflow-hidden rounded-2xl border border-[#172B52] bg-[#061027]/70 backdrop-blur-sm">
          <div className="flex items-center justify-between border-b border-[#172B52] px-6 py-5 md:px-8">
            <div>
              <p className="text-xs uppercase tracking-widest text-[#596783]">
                Example benchmark run
              </p>
              <h3 className="mt-1 text-lg font-semibold text-white">
                Agent evaluation
              </h3>
            </div>
            <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs font-medium text-emerald-400">
              SUCCESS
            </span>
          </div>

          <div className="flex flex-wrap gap-x-10 gap-y-6 px-6 py-6 md:px-8">
            {[
              { label: "Environment", value: "Synthetic AD" },
              { label: "Target", value: "Domain Admin" },
              { label: "Steps", value: "8" },
              { label: "Path length", value: "6 nodes" },
              { label: "Efficiency", value: "87%", accent: true },
            ].map((stat) => (
              <div key={stat.label}>
                <p className="text-xs text-[#596783]">{stat.label}</p>
                <p
                  className={`mt-2 text-lg font-semibold ${
                    stat.accent ? "text-[#A78BFA]" : "text-white"
                  }`}
                >
                  {stat.value}
                </p>
              </div>
            ))}
          </div>

          <div className="border-t border-[#172B52] px-6 py-4 text-xs text-[#596783] md:px-8">
            Example output — actual benchmark results are generated by Ariadne.
          </div>
        </div>

      </div>
    </section>
  );
};

export default BenchmarkSection;