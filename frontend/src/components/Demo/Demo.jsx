import React, { useEffect, useState } from "react";
import AriadneLogo from "../../assets/images/AriadneLogo_animated.svg";
import { FaCircle, FaCheck } from "react-icons/fa";

const TRACE = [
  "Loading BloodHound environment...",
  "Parsing Active Directory objects...",
  "Building graph...",
  "Searching candidate paths...",
  "Evaluating relationships...",
  "Verifying transition...",
  "Attack path discovered.",
];

const LINE_INTERVAL = 900;
const RESULT_DELAY = 500;
const LOOP_PAUSE = 3200;

const Demo = () => {
  const [visibleCount, setVisibleCount] = useState(1);
  const [showResult, setShowResult] = useState(false);

  useEffect(() => {
    if (visibleCount < TRACE.length) {
      const timer = setTimeout(() => {
        setVisibleCount((count) => count + 1);
      }, LINE_INTERVAL);

      return () => clearTimeout(timer);
    }

    const resultTimer = setTimeout(() => {
      setShowResult(true);
    }, RESULT_DELAY);

    const loopTimer = setTimeout(() => {
      setShowResult(false);
      setVisibleCount(1);
    }, LOOP_PAUSE);

    return () => {
      clearTimeout(resultTimer);
      clearTimeout(loopTimer);
    };
  }, [visibleCount]);

  const isComplete = visibleCount >= TRACE.length;

  return (
    <section className="relative min-h-screen overflow-hidden bg-[#020817] text-white py-16 md:py-20">
      
      {/* ================= BACKGROUND ================= */}

      <div className="absolute inset-0 pointer-events-none">

        {/* Main radial glow */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_45%,rgba(91,63,180,0.12),transparent_38%)]" />

        {/* Left glow */}
        <div className="absolute top-1/4 left-0 w-[400px] h-[400px] bg-[#2447A8]/10 blur-[140px] rounded-full" />

        {/* Bottom-right glow */}
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] bg-[#6D4AFF]/10 blur-[140px] rounded-full" />

      </div>

      {/* ================= CONTENT ================= */}

      <div className="relative z-10 max-w-7xl mx-auto px-6 md:px-10 lg:px-16">

        {/* ================= HEADER ================= */}

        <div className="max-w-2xl">

          {/* Live badge */}


          {/* Heading */}

          <h2 className="mt-6 text-3xl md:text-4xl lg:text-5xl font-bold tracking-tight text-white leading-tight">

            Watch Ariadne reason through an{" "}

            <span className="bg-gradient-to-r from-[#7C5CFF] via-[#9B83E2] to-[#7D94F0] bg-clip-text text-transparent">
              attack path.
            </span>

          </h2>

          {/* Description */}

          <p className="mt-5 text-sm md:text-base leading-7 text-[#8E9AB3]">

            Upload a BloodHound environment and watch Ariadne analyze the
            graph, investigate possible paths, verify each transition, and
            produce an explainable result.

          </p>

        </div>

        {/* ================= MAIN VISUAL ================= */}

        <div className="mt-8 grid lg:grid-cols-[1.15fr_1fr] gap-14 lg:gap-10 items-center">

          {/* ================= LEFT — TERMINAL ================= */}

          <div className="order-2 lg:order-1">

            {/* Status row */}

            <div className="flex items-center justify-between mb-4">

              <div className="flex items-center gap-2.5">

                <span className="relative flex h-2 w-2">

                  <span
                    className={`absolute inline-flex  opacity-50 ${
                      isComplete ? "" : "animate-ping"
                    }`}
                  />


                </span>

                <span className="text-xs font-mono tracking-[0.15em] uppercase text-[#8996B1]">
                  {isComplete ? "Path verified" : "Agent active"}
                </span>

              </div>


            </div>

            {/* Terminal */}

            <div className="rounded-xl border border-[#172B52] bg-[#040A18] shadow-[0_20px_60px_-20px_rgba(0,0,0,0.6)]">

              {/* Terminal header */}

              <div className="flex items-center gap-2 px-6 py-2 border-b border-[#0F1B38]">

                <span className="w-2.5 h-2.5 rounded-full bg-[#29345C]" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#29345C]" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#29345C]" />

                <span className="ml-3 text-[11px] font-mono text-[#596783]">
                  ariadne — investigation
                </span>

              </div>

              {/* Terminal content */}

              <div className="px-6 py-6">

                <div className="flex flex-col gap-3 font-mono text-[13px] md:text-sm min-h-[196px]">

                  {TRACE.slice(0, visibleCount).map((line, i) => {

                    const isLast = i === visibleCount - 1;

                    const isFinal =
                      i === TRACE.length - 1 && isComplete;

                    return (
                      <div
                        key={line}
                        className="flex items-start gap-3 animate-[fadeIn_0.4s_ease-out]"
                      >

                        {/* Line number */}

                        <span className="text-[#596783] shrink-0 pt-0.5">
                          {String(i + 1).padStart(2, "0")}
                        </span>

                        {/* Status icon */}

                        <span className="shrink-0 pt-1">

                          {isFinal ? (
                            <FaCheck
                              size={10}
                              className="text-[#8B7CFF]"
                            />
                          ) : isLast ? (
                            <FaCircle
                              size={7}
                              className="text-[#7C5CFF] animate-pulse"
                            />
                          ) : (
                            <FaCheck
                              size={10}
                              className="text-[#4A4F73]"
                            />
                          )}

                        </span>

                        {/* Trace text */}

                        <span
                          className={
                            isFinal
                              ? "text-[#B7C0D5]"
                              : isLast
                              ? "text-[#9DA9C2]"
                              : "text-[#596783]"
                          }
                        >
                          {line}
                        </span>

                      </div>
                    );
                  })}

                </div>

                {/* ================= RESULT SUMMARY ================= */}

                <div
                  className={`mt-5 pt-5 border-t border-[#0F1B38] flex flex-wrap items-center gap-x-8 gap-y-2 transition-opacity duration-500 ${
                    showResult ? "opacity-100" : "opacity-0"
                  }`}
                >

                  {/* Target */}

                  <div>
                    <p className="text-[10px] font-mono uppercase tracking-widest text-[#596783]">
                      Target reached
                    </p>

                    <p className="mt-1 text-sm font-mono text-[#B7C0D5]">
                      Domain Admin
                    </p>
                  </div>

                  {/* Path length */}

                  <div>
                    <p className="text-[10px] font-mono uppercase tracking-widest text-[#596783]">
                      Path length
                    </p>

                    <p className="mt-1 text-sm font-mono text-[#B7C0D5]">
                      4 hops
                    </p>
                  </div>

                  {/* Verification */}

                  <div>
                    <p className="text-[10px] font-mono uppercase tracking-widest text-[#596783]">
                      Verification
                    </p>

                    <p className="mt-1 text-sm font-mono text-[#8B7CFF]">
                      Passed
                    </p>
                  </div>

                </div>

              </div>

            </div>

            {/* Disclaimer */}

            <p className="mt-3 text-[11px] text-[#4A4F73] font-mono">
              Simulated investigation sequence — visual demonstration only.
            </p>

          </div>

          {/* ================= RIGHT — ANIMATED LOGO ================= */}


          <div className="order-1 lg:order-2 flex items-center justify-center">

            <div className="relative flex items-center justify-center min-h-[420px] md:min-h-[560px]">

              {/* Large glow */}

              <div
                className="
                  absolute
                  w-[360px]
                  h-[360px]
                  md:w-[520px]
                  md:h-[520px]
                  rounded-full
                  bg-[#6D4AFF]/15
                  blur-[110px]
                "
              />

              {/* Outer rotating ring */}

              <div
                className="
                  absolute
                  w-[300px]
                  h-[300px]
                  md:w-[440px]
                  md:h-[440px]
                  rounded-full
                  border
                  border-[#29345C]/60
                  animate-[spin_20s_linear_infinite]
                "
              />

              {/* Inner rotating ring */}

              <div
                className="
                  absolute
                  w-[260px]
                  h-[260px]
                  md:w-[380px]
                  md:h-[380px]
                  rounded-full
                  border
                  border-[#7C5CFF]/20
                "
              />

              {/* Logo */}

              <img
                src={AriadneLogo}
                alt="Ariadne"
                className="
                  relative
                  z-10
                  w-[260px]
                  md:w-[400px]
                  h-auto
                  drop-shadow-[0_0_55px_rgba(124,92,255,0.45)]
                "
              />

            </div>

          </div>

        </div>

      </div>

      {/* ================= ANIMATION ================= */}

      <style>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(4px);
          }

          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>

    </section>
  );
};

export default Demo;