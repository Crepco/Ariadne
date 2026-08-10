import { useState, useEffect, useRef } from "react";
import { FaGithub, FaBars, FaTimes } from "react-icons/fa";
import { Link, useLocation } from "react-router-dom";

const NAV_LINKS = [
  { href: "#working", label: "How It Works" },
  { href: "#features", label: "Features" },
  { href: "/demo", label: "Demo" },
  { href: "/benchmark", label: "Benchmark" },
];

const Navbar = () => {
  const location = useLocation();

  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [activeSection, setActiveSection] = useState("");
  const [hovered, setHovered] = useState(null);

  const linkRefs = useRef({});
  const [threadStyle, setThreadStyle] = useState({
    opacity: 0,
  });

  const isHomePage = location.pathname === "/";

  /* ---------------------------------------
     SCROLL DETECTION
  --------------------------------------- */

  useEffect(() => {
    const onScroll = () => {
      setScrolled(window.scrollY > 12);
    };

    onScroll();

    window.addEventListener("scroll", onScroll, {
      passive: true,
    });

    return () => {
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  /* ---------------------------------------
     ACTIVE SECTION DETECTION
     Only runs on Home page
  --------------------------------------- */

  useEffect(() => {
    if (!isHomePage) {
      setActiveSection("");
      return;
    }

    const sections = NAV_LINKS
      .filter((link) => link.href.startsWith("#"))
      .map((link) => document.querySelector(link.href))
      .filter(Boolean);

    if (!sections.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveSection(`#${entry.target.id}`);
          }
        });
      },
      {
        rootMargin: "-45% 0px -45% 0px",
        threshold: 0,
      }
    );

    sections.forEach((section) => {
      observer.observe(section);
    });

    return () => {
      observer.disconnect();
    };
  }, [isHomePage, location.pathname]);

  /* ---------------------------------------
     ARIADNE'S THREAD
  --------------------------------------- */

  useEffect(() => {
    const key = hovered ?? activeSection;
    const element = linkRefs.current[key];

    if (element) {
      setThreadStyle({
        left: element.offsetLeft,
        width: element.offsetWidth,
        opacity: 1,
      });
    } else {
      setThreadStyle((style) => ({
        ...style,
        opacity: 0,
      }));
    }
  }, [hovered, activeSection, location.pathname]);

  /* ---------------------------------------
     CLOSE MOBILE MENU
  --------------------------------------- */

  const closeMenu = () => {
    setMenuOpen(false);
  };

  /* ---------------------------------------
     HANDLE NAVIGATION
  --------------------------------------- */

  const getLink = (href) => {
    /*
      If we're already on Home:
        #about → #about

      If we're on Demo:
        #about → /#about
    */

    if (href.startsWith("#")) {
      return isHomePage ? href : `/${href}`;
    }

    return href;
  };

  return (
    <nav className="sticky top-0 z-50 w-full">

      {/* =====================================================
          MAIN NAVBAR
      ===================================================== */}

      <div
        className={`w-full px-6 md:px-10 lg:px-16 flex items-center justify-between border-b transition-all duration-300 ${
          scrolled
            ? "py-3 bg-[#020817]/95 backdrop-blur-xl border-[#091120] shadow-[0_4px_30px_rgba(2,10,30,0.6)]"
            : "py-5 bg-[#030B1C]/95 backdrop-blur-md border-[#081224]"
        }`}
      >

        {/* ===================================================
            LOGO
        =================================================== */}

        <Link
          to="/"
          onClick={() => {
            closeMenu();
            setActiveSection("");
          }}
          className="flex items-center gap-3 group"
        >
          <div className="leading-none">

            <div className="text-[#F5F7FF] text-[20px] md:text-[22px] font-bold tracking-wide">
              ARIADNE
            </div>

            <div className="mt-1 text-[10px] md:text-[11px] text-[#A8B3CC] tracking-wide">
              LLM Agent for AD Attack Paths
            </div>

          </div>
        </Link>

        {/* ===================================================
            DESKTOP NAVIGATION
        =================================================== */}

        <div
          className="hidden lg:flex items-center gap-1 relative"
          onMouseLeave={() => setHovered(null)}
        >

          {/* Ariadne's Thread */}

          <span
            className="absolute -bottom-1 h-[2px] rounded-full bg-gradient-to-r from-[#7C5CFF] to-[#9B7BFF] shadow-[0_0_10px_rgba(124,92,255,0.8)] transition-all duration-300 ease-out pointer-events-none"
            style={threadStyle}
          />

          {NAV_LINKS.map((link) => {

            const destination = getLink(link.href);

            const isActive =
              activeSection === link.href ||
              (link.href === "/demo" && location.pathname === "/demo")||
              (link.href === "/benchmark" && location.pathname === "/benchmark");
              

            /*
              Hash links use <a>
              Route links use React Router <Link>
            */

            if (link.href.startsWith("#")) {
              return (
                <a
                  key={link.href}
                  href={destination}
                  ref={(element) => {
                    linkRefs.current[link.href] = element;
                  }}
                  onMouseEnter={() => setHovered(link.href)}
                  className={`px-4 py-2 text-[15px] transition-colors duration-200 ${
                    isActive
                      ? "text-white"
                      : "text-[#D5DCEF] hover:text-[#B8A7FF]"
                  }`}
                >
                  {link.label}
                </a>
              );
            }

            return (
              <Link
                key={link.href}
                to={destination}
                ref={(element) => {
                  linkRefs.current[link.href] = element;
                }}
                onMouseEnter={() => setHovered(link.href)}
                className={`px-4 py-2 text-[15px] transition-colors duration-200 ${
                  isActive
                    ? "text-white"
                    : "text-[#D5DCEF] hover:text-[#B8A7FF]"
                }`}
              >
                {link.label}
              </Link>
            );
          })}

        </div>

        {/* ===================================================
            DESKTOP RIGHT SIDE
        =================================================== */}

        <div className="hidden lg:flex items-center gap-6">

          {/* GitHub */}

          <a
            href="https://github.com/Crepco/Ariadne"
            target="_blank"
            rel="noreferrer"
            aria-label="GitHub"
            className="text-[#D5DCEF] hover:text-[#A78BFA] transition-all duration-200 hover:drop-shadow-[0_0_10px_rgba(124,92,255,0.6)] hover:-translate-y-0.5"
          >
            <FaGithub size={20} />
          </a>

          {/* Get Started */}

          {isHomePage ? (
            <a
              href="#benchmark"
              className="px-5 py-2 rounded-lg bg-gradient-to-r from-[#6D4AFF] to-[#825CFF] text-white text-sm font-semibold shadow-[0_0_25px_rgba(109,74,255,0.3)] hover:shadow-[0_0_35px_rgba(109,74,255,0.55)] hover:brightness-110 active:scale-[0.97] transition-all duration-300"
            >
              Get Started
            </a>
          ) : (
            <Link
              to="/#benchmark"
              className="px-5 py-2 rounded-lg bg-gradient-to-r from-[#6D4AFF] to-[#825CFF] text-white text-sm font-semibold shadow-[0_0_25px_rgba(109,74,255,0.3)] hover:shadow-[0_0_35px_rgba(109,74,255,0.55)] hover:brightness-110 active:scale-[0.97] transition-all duration-300"
            >
              Get Started
            </Link>
          )}

        </div>

        {/* ===================================================
            MOBILE HAMBURGER
        =================================================== */}

        <div className="lg:hidden flex items-center">

          <button
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            className="w-10 h-10 flex items-center justify-center rounded-lg text-[#D5DCEF] hover:text-[#A78BFA] hover:bg-[#102044] transition-all duration-200 active:scale-95"
          >
            <span
              className={`inline-flex transition-transform duration-200 ${
                menuOpen ? "rotate-90" : "rotate-0"
              }`}
            >
              {menuOpen ? (
                <FaTimes size={21} />
              ) : (
                <FaBars size={21} />
              )}
            </span>
          </button>

        </div>

      </div>

      {/* =====================================================
          MOBILE MENU
      ===================================================== */}

      <div
        className={`lg:hidden overflow-hidden transition-[max-height,opacity] duration-300 ease-out bg-[#081633]/98 backdrop-blur-xl border-b border-[#172B52] ${
          menuOpen
            ? "max-h-[520px] opacity-100"
            : "max-h-0 opacity-0"
        }`}
      >

        <div className="flex flex-col gap-1 px-6 py-5">

          {NAV_LINKS.map((link, index) => {

            const destination = getLink(link.href);

            const isActive =
              activeSection === link.href ||
              (link.href === "/demo" &&
                location.pathname === "/demo");

            return (
              <Link
                key={link.href}
                to={destination}
                onClick={closeMenu}
                style={{
                  transitionDelay: menuOpen
                    ? `${index * 40}ms`
                    : "0ms",
                }}
                className={`px-4 py-3 rounded-lg transition-all duration-300 ${
                  menuOpen
                    ? "translate-x-0 opacity-100"
                    : "-translate-x-2 opacity-0"
                } ${
                  isActive
                    ? "text-white bg-[#060d1d]"
                    : "text-[#D5DCEF] hover:text-[#A78BFA] hover:bg-[#102044]"
                }`}
              >
                {link.label}
              </Link>
            );
          })}

          <div className="h-px bg-[#172B52] my-3" />

          <div className="flex items-center gap-3">

            {/* =================================================
                MOBILE GITHUB
            ================================================= */}

            <a
              href="https://github.com/Crepco/Ariadne"
              target="_blank"
              rel="noreferrer"
              onClick={closeMenu}
              aria-label="GitHub"
              className="flex-1 flex items-center justify-center gap-2 px-5 py-3 rounded-lg border border-[#29345C] bg-[#081633] text-[#D5DCEF] hover:text-[#A78BFA] hover:border-[#6954B8] hover:bg-[#102044] transition-all"
            >
              <FaGithub size={18} />
              <span>GitHub</span>
            </a>

            {/* =================================================
                MOBILE GET STARTED
            ================================================= */}

            {isHomePage ? (
              <a
                href="#benchmark"
                onClick={closeMenu}
                className="flex-1 text-center px-5 py-3 rounded-lg bg-gradient-to-r from-[#6D4AFF] to-[#825CFF] text-white font-semibold shadow-[0_0_20px_rgba(109,74,255,0.25)] active:scale-[0.98] transition-transform"
              >
                Get Started
              </a>
            ) : (
              <Link
                to="/#benchmark"
                onClick={closeMenu}
                className="flex-1 text-center px-5 py-3 rounded-lg bg-gradient-to-r from-[#6D4AFF] to-[#825CFF] text-white font-semibold shadow-[0_0_20px_rgba(109,74,255,0.25)] active:scale-[0.98] transition-transform"
              >
                Get Started
              </Link>
            )}

          </div>

        </div>

      </div>

    </nav>
  );
};

export default Navbar;