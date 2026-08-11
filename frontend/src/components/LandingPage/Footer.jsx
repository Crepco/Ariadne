import React from "react";
import { FaGithub, FaArrowUp } from "react-icons/fa6";

const Footer = () => {
  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  return (
    <footer className="relative border-t border-slate-800/80 bg-[#020817] px-6 text-slate-300 overflow-hidden">
      {/* Top Accent Gradient Border */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 h-[1px] w-3/4 bg-gradient-to-r from-transparent via-cyan-500/40 to-transparent" />

      {/* Ambient Radial Backlight Glow */}
      <div className="pointer-events-none absolute bottom-0 right-1/4 h-64 w-64 rounded-full bg-cyan-500/5 blur-[120px]" />

      <div className="mx-auto max-w-7xl py-16 relative z-10">
        <div className="grid gap-12 md:grid-cols-[2fr_1fr_1fr_1fr]">
          {/* Brand */}
          <div className="space-y-4">
            <h2 className="text-2xl font-bold tracking-tight text-white">
              Ariadne<span className="hover:text-[#6D4AFF] drop-shadow-[0_0_8px_rgba(34,211,238,0.5)]">.</span>
            </h2>

            <p className="max-w-sm text-sm leading-relaxed text-slate-400">
              A benchmark for evaluating how AI agents navigate complex
              Active Directory attack paths.
            </p>

            <a
              href="https://github.com/Humera-tech"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/50 px-3.5 py-2 text-xs font-medium text-slate-300 transition-all duration-200 hover:border-cyan-500/40 hover:bg-slate-800/60 hover:text-[#6D4AFF] hover:shadow-[0_0_12px_rgba(34,211,238,0.15)]"
            >
              <FaGithub className="text-sm" />
              GitHub Repository
            </a>
          </div>

          {/* Navigation Column 1 */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              Explore
            </h3>

            <div className="mt-5 flex flex-col gap-3 text-sm text-slate-400">
              <a href="/" className="transition-colors duration-200 hover:text-[#6D4AFF]">
                What is Ariadne
              </a>
              <a href="#working" className="transition-colors duration-200 hover:text-[#6D4AFF]">
                How it works
              </a>
              <a href="#features" className="transition-colors duration-200 hover:text-[#6D4AFF]">
                Features
              </a>
              <a href="/benchmark" className="transition-colors duration-200 hover:text-[#6D4AFF]">
                Benchmark
              </a>
            </div>
          </div>

          {/* Navigation Column 2 */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              Resources
            </h3>

            <div className="mt-5 flex flex-col gap-3 text-sm text-slate-400">
              <a href="/docs" className="transition-colors duration-200 hover:text-[#6D4AFF]">
                Documentation
              </a>
              <a
                href="https://github.com/Humera-tech"
                target="_blank"
                rel="noopener noreferrer"
                className="transition-colors duration-200 hover:text-[#6D4AFF]"
              >
                GitHub
              </a>
              <a href="/demo" className="transition-colors duration-200 hover:text-[#6D4AFF]">
                Live Demo
              </a>
            </div>
          </div>

          {/* Navigation Column 3 */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              Product
            </h3>

            <div className="mt-5 flex flex-col gap-3 text-sm text-slate-400">
              <a href="/demo" className="transition-colors duration-200 hover:text-[#6D4AFF]">
                Get Started
              </a>
              <a href="/benchmark" className="transition-colors duration-200 hover:text-[#6D4AFF]">
                Benchmark Leaderboard
              </a>
            </div>
          </div>
        </div>

        {/* Centered Bottom Bar */}
        <div className="mt-16 grid grid-cols-1 gap-4 border-t border-slate-800/80 pt-8 text-xs text-slate-500 md:grid-cols-3 md:items-center">
          {/* Spacer for 3-column balance on desktop */}
          <div className="hidden md:block" />

          {/* Centered Copyright Notice */}
          <p className="text-center">
            © {new Date().getFullYear()} Ariadne. Built for AI security research.
          </p>

          {/* Right-aligned Button */}
          <div className="flex justify-center md:justify-end">
            <button
              onClick={scrollToTop}
              className="group inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-400 transition-all duration-200 hover:border-cyan-500/40 hover:text-[#6D4AFF] hover:shadow-[0_0_12px_rgba(34,211,238,0.15)]"
            >
              Back to top
              <FaArrowUp className="text-[10px] transition-transform duration-200 group-hover:-translate-y-0.5" />
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;