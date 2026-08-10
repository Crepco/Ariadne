import React from "react";
import AriadneGraph from "../../assets/images/AriadneGraph.svg";

const HeroSection = () => {
  return (
    <section className="relative min-h-screen overflow-hidden bg-[#020817] flex items-center pt-28 pb-20">

      {/* Background Glow */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_45%,rgba(91,63,180,0.14),transparent_38%)] pointer-events-none"></div>

      <div className="absolute top-1/4 left-0 w-[400px] h-[400px] bg-[#2447A8]/10 blur-[140px] rounded-full pointer-events-none"></div>

      {/* Content */}
      <div className="relative z-10 w-full max-w-7xl mx-auto px-6 md:px-10 lg:px-16">

        <div className="grid lg:grid-cols-[0.8fr_1.2fr] gap-12 lg:gap-20 items-center">

          {/* ================= LEFT ================= */}

          <div className="max-w-2xl">


            {/* Heading */}
            <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold leading-[1.05] tracking-tight text-white">

              Autonomous
              <br />

              <span className="bg-gradient-to-r from-[#6048b4] via-[#8270b8] to-[#96a9f7] bg-clip-text text-transparent">
                Attack Path
              </span>

              <br />

              Reasoning

            </h1>

            {/* Product Name */}
            <div className="mt-7 text-xl md:text-2xl font-semibold text-[#E8EBF5]">
              Ariadne
            </div>

            {/* Description */}
            <p className="mt-4 max-w-xl text-base md:text-lg leading-8 text-[#9DA9C2]">
              An LLM agent that autonomously investigates Active Directory
              environments, discovers hidden attack paths, verifies every
              step, and explains how to reach Domain Admin.
            </p>

            {/* Buttons */}
            <div className="flex flex-wrap items-center gap-4 mt-8">

              <a
                href="#benchmark"
                className="px-6 py-3 rounded-lg bg-gradient-to-r from-[#6D4AFF] to-[#825CFF] text-white font-semibold text-sm shadow-[0_0_30px_rgba(109,74,255,0.25)] hover:shadow-[0_0_40px_rgba(109,74,255,0.45)] hover:brightness-110 active:scale-[0.97] transition-all duration-300"
              >
                Upload BloodHound ZIP
              </a>

              <a
                href="#demo"
                className="px-6 py-3 rounded-lg border border-[#29345C] bg-[#08132B]/70 text-[#E5E9F5] font-semibold text-sm hover:border-[#6954B8] hover:text-white hover:bg-[#101B38] active:scale-[0.97] transition-all duration-300"
              >
                Watch Demo
              </a>

            </div>

            {/* Small credibility text */}
            <div className="flex items-center gap-6 mt-8 text-xs text-[#697693]">
              <span>BloodHound Compatible</span>
              <span className="w-1 h-1 rounded-full bg-[#4B5875]"></span>
              <span>Neo4j Graph Engine</span>
              <span className="w-1 h-1 rounded-full bg-[#4B5875]"></span>
              <span>LLM Agent</span>
            </div>

          </div>


          {/* ================= RIGHT ================= */}

          <div className="relative flex items-center justify-center">

            {/* Graph Glow */}
            <div className="absolute w-[500px] h-[500px] bg-[#6946FF]/10 blur-[100px] rounded-full"></div>

            {/* Graph Container */}
            <div className="relative w-full max-w-[900px]">

              {/* Outer border */}
              <div className="absolute inset-0 rounded-3xl  backdrop-blur-sm"></div>

              {/* Graph */}
              <div className="relative p-5 md:p-12">

                <img
                  src={AriadneGraph}
                  alt="Ariadne Active Directory attack path graph"
                  className="relative z-10 w-full h-auto object-contain drop-shadow-[0_0_30px_rgba(103,78,255,0.25)]"
                />

              </div>              

            </div>

          </div>

        </div>

      </div>

    </section>
  );
};

export default HeroSection;