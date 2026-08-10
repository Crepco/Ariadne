import React, { useState } from "react";
import { FaBrain, FaProjectDiagram, FaShieldAlt, FaSearch, FaRoute, FaFileAlt } from "react-icons/fa";

const FEATURES = [
  { icon: FaBrain, code: "REASONING", title: "LLM-powered reasoning", description: "An autonomous agent evaluates Active Directory topology and determines high-value paths." },
  { icon: FaProjectDiagram, code: "TOPOLOGY", title: "Graph-based analysis", description: "Builds a live graph of users, service accounts, domain controllers, and privilege hierarchies." },
  { icon: FaSearch, code: "DISCOVERY", title: "Attack path discovery", description: "Simulates stealth movement vectors to surface transitive escalation routes to Domain Admin." },
  { icon: FaShieldAlt, code: "VERIFICATION", title: "Deterministic verification", description: "Cross-references every lateral movement step against explicit AD access control rules." },
  { icon: FaRoute, code: "TELEMETRY", title: "Step-by-step investigation", description: "Deconstructs attack paths into granular, inspectable state changes across the domain." },
  { icon: FaFileAlt, code: "FORENSICS", title: "Explainable results", description: "Generates natural-language rationale alongside structural evidence for fast remediation." },
];

const Features = () => {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  return (
    <section
      id="features"
      onMouseMove={handleMouseMove}
      className="relative overflow-hidden bg-[#020817] py-16 md:py-20"
    >

      {/* Telemetry mesh — this section's own signature, not reused elsewhere */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f293712_1px,transparent_1px),linear-gradient(to_bottom,#1f293712_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)]" />

      <div className="relative z-10 max-w-7xl mx-auto px-6 md:px-10 lg:px-16">

        {/* Section Header */}
        <div className="max-w-2xl mx-auto text-center">
            <p className="text-xs md:text-sm font-semibold tracking-[0.25em] uppercase text-[#7C5CFF] m-2">
            Features
          </p>
          <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight text-white leading-tight">
            Built to reason,{" "}
            <span className="bg-gradient-to-r from-[#A78BFA] via-[#60A5FA] to-[#34D399] bg-clip-text text-transparent">
              not just search through noise.
            </span>
          </h2>

          <p className="mt-4 text-sm md:text-base leading-relaxed text-slate-400 font-light">
            Ariadne merges deterministic graph analysis with contextual LLM reasoning to validate Active Directory attack vectors.
          </p>
        </div>

        {/* Feature Grid — dense HUD cards, not glow-blur cards */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mt-12">
          {FEATURES.map((feature) => {
            const Icon = feature.icon;
            return (
              <div
                key={feature.title}
                className="group relative rounded-xl border border-slate-800/80 bg-slate-950/50 p-5 transition-all duration-300 hover:border-[#7C5CFF]/50 hover:bg-slate-900/60"
              >
                {/* Index bar — thin, top-mounted, reads as a data-card header rather than decoration */}
                <div className="flex items-center justify-between mb-4">
                  <span className="text-[10px] font-mono tracking-wider text-slate-500 group-hover:text-[#A78BFA] transition-colors">
                    {feature.code}
                  </span>
                </div>

                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 shrink-0 rounded-lg flex items-center justify-center bg-slate-900 border border-slate-800 text-[#A78BFA] group-hover:border-[#7C5CFF]/60 group-hover:bg-[#7C5CFF]/10 group-hover:text-white transition-all duration-300">
                    <Icon size={16} />
                  </div>
                  <div>
                    <h3 className="text-[15px] font-semibold text-slate-100 group-hover:text-white transition-colors leading-tight">
                      {feature.title}
                    </h3>
                    <p className="mt-1.5 text-[13px] leading-6 text-slate-400">
                      {feature.description}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Terminal readout — replaces the pill-and-arrow banner (that pattern already belongs to How It Works) */}
        <div className="mt-12">
          <div className="rounded-xl border border-slate-800 bg-[#03060f] px-5 py-4 font-mono">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-2 text-[13px]">
              <span className="text-slate-600">$</span>
              <span className="text-slate-400">validation_loop</span>
              <span className="text-slate-600">--stages</span>
              <span className="text-indigo-400">reason</span>
              <span className="text-slate-700">→</span>
              <span className="text-blue-400">verify</span>
              <span className="text-slate-700">→</span>
              <span className="text-emerald-400">explain</span>
            </div>
            <p className="mt-2.5 text-[13px] text-slate-500 font-sans leading-relaxed">
              Generative reasoning is sandwiched between strict graph-state queries and ACL rule checks, eliminating hallucination risk.
            </p>
          </div>
        </div>

      </div>
    </section>
  );
};

export default Features;