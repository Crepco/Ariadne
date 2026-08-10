import React from "react";
import {
  FaCloudUploadAlt,
  FaProjectDiagram,
  FaRoute,
  FaRobot,
  FaShieldAlt,
  FaFileAlt,
} from "react-icons/fa";

const STEPS = [
  {
    number: "01",
    title: "Upload Data",
    subtitle: "Start with your BloodHound data",
    description:
      "Upload a BloodHound ZIP containing information about users, groups, computers, permissions, and relationships.",
    tags: ["BloodHound", "ZIP Upload", "AD Data"],
    icon: FaCloudUploadAlt,
  },
  {
    number: "02",
    title: "Parse Data",
    subtitle: "Understand the environment",
    description:
      "Ariadne reads the uploaded data and extracts the important Active Directory objects and relationships.",
    tags: ["AD Objects", "Relationships", "Parser"],
    icon: FaProjectDiagram,
  },
  {
    number: "03",
    title: "Build Graph",
    subtitle: "Create the AD graph",
    description:
      "The extracted data is organized into a graph so Ariadne can explore how users, groups, computers, and permissions are connected.",
    tags: ["Neo4j", "Graph", "BloodHound Schema"],
    icon: FaRoute,
  },
  {
    number: "04",
    title: "AI Investigation",
    subtitle: "Explore possible attack paths",
    description:
      "The LLM agent explores the graph, reasons about relationships, and searches for possible paths toward the target.",
    tags: ["LLM Agent", "Reasoning", "Path Search"],
    icon: FaRobot,
  },
  {
    number: "05",
    title: "Verify Path",
    subtitle: "Check every step",
    description:
      "Ariadne verifies each step against the graph and security rules to make sure the discovered path is actually possible.",
    tags: ["Verification", "Security Rules", "Validation"],
    icon: FaShieldAlt,
  },
  {
    number: "06",
    title: "Get Results",
    subtitle: "Understand the discovered path",
    description:
      "Ariadne presents the discovered attack path with explanations, making the result easier to understand and evaluate.",
    tags: ["Attack Path", "Explanation", "Report"],
    icon: FaFileAlt,
  },
];

const HowItWorks = () => {
  return (
    <section
      id="working"
      className="relative overflow-hidden py-20 md:py-24 bg-[#020817]"
    >
      {/* ================= BACKGROUND GLOW ================= */}

      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[400px] bg-[#4C3A9E]/10 blur-[140px] rounded-full" />

        <div className="absolute bottom-0 right-0 w-[450px] h-[450px] bg-[#2447A8]/10 blur-[150px] rounded-full" />
      </div>

      {/* ================= CONTENT ================= */}

      <div className="relative z-10 max-w-7xl mx-auto px-6 md:px-10 lg:px-16">

        {/* ================= HEADER ================= */}

        <div className="max-w-2xl mx-auto text-center">

          <p className="text-xs font-mono tracking-[0.25em] text-[#7C5CFF] uppercase">
            How It Works
          </p>

          <h2 className="mt-4 text-3xl md:text-4xl font-extrabold tracking-tight text-white leading-tight">
            From data to{" "}
            <span className="bg-gradient-to-r from-[#A78BFA] via-[#60A5FA] to-[#7D94F0] bg-clip-text text-transparent">
              Domain Admin
            </span>
          </h2>

          <p className="mt-4 text-sm md:text-base leading-relaxed text-[#8E9AB3] font-light">
            Ariadne takes your Active Directory data, investigates it with an
            AI agent, verifies every step, and finds meaningful attack paths
            through the environment.
          </p>

        </div>

        {/* ================= PROCESS ================= */}

        <div className="relative mt-12">

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">

            {STEPS.map((step, index) => {

              const Icon = step.icon;

              return (
                <div
                  key={step.number}
                  className="group relative flex flex-col"
                >


                  {/* ================= NUMBER ================= */}

                  <div className="relative z-10 flex items-center gap-3">

                    <div
                      className="
                        w-[54px]
                        h-[54px]
                        shrink-0
                        rounded-full
                        bg-[#061229]
                        border
                        border-[#29345C]
                        flex
                        items-center
                        justify-center
                        transition-all
                        duration-300
                        group-hover:border-[#7C5CFF]
                        group-hover:shadow-[0_0_24px_rgba(124,92,255,0.25)]
                      "
                    >
                      <span
                        className="
                          text-base
                          font-bold
                          bg-gradient-to-r
                          from-[#7C5CFF]
                          to-[#9B7BFF]
                          bg-clip-text
                          text-transparent
                        "
                      >
                        {step.number}
                      </span>
                    </div>

                    {/* Mobile step label */}

                    <span
                      className="
                        lg:hidden
                        text-[11px]
                        font-medium
                        tracking-widest
                        text-[#5E6C93]
                        uppercase
                      "
                    >
                      Step {step.number}
                    </span>

                  </div>

                  {/* ================= CARD ================= */}

                  <div
                    className="
                      mt-5
                      flex
                      flex-1
                      flex-col
                      rounded-2xl
                      border
                      border-[#172B52]
                      bg-[#061027]/70
                      backdrop-blur-sm
                      p-5
                      transition-all
                      duration-300
                      group-hover:-translate-y-1
                      group-hover:border-[#293A68]
                      group-hover:bg-[#08142E]
                      group-hover:shadow-[0_15px_40px_rgba(0,0,0,0.25)]
                    "
                  >

                    {/* ================= TITLE + ICON ================= */}

                    <div className="flex items-center gap-3">

                      <div
                        className="
                          w-10
                          h-10
                          shrink-0
                          rounded-lg
                          bg-[#0B1833]
                          border
                          border-[#29345C]
                          flex
                          items-center
                          justify-center
                          transition-all
                          duration-300
                          group-hover:border-[#7C5CFF]
                          group-hover:bg-[#101D40]
                        "
                      >
                        <Icon
                          size={18}
                          className="
                            text-[#8B7CFF]
                            transition-transform
                            duration-300
                            group-hover:scale-110
                          "
                        />
                      </div>

                      <h3 className="text-xl font-bold text-white">
                        {step.title}
                      </h3>

                    </div>

                    {/* ================= SUBTITLE ================= */}

                    <p className="mt-3 text-sm font-medium text-[#8F7CFF]">
                      {step.subtitle}
                    </p>

                    {/* ================= DESCRIPTION ================= */}

                    <p className="mt-4 text-sm leading-7 text-[#8E9AB3] flex-1">
                      {step.description}
                    </p>

                    {/* ================= TAGS ================= */}

                    <div
                      className="
                        flex
                        flex-wrap
                        gap-2
                        mt-6
                        pt-5
                        border-t
                        border-[#141F3D]
                      "
                    >
                      {step.tags.map((tag) => (
                        <span
                          key={tag}
                          className="
                            px-2.5
                            py-1
                            rounded-md
                            bg-[#0B1833]
                            border
                            border-[#1B2A4B]
                            text-[10px]
                            font-medium
                            tracking-wide
                            text-[#8996B1]
                          "
                        >
                          {tag}
                        </span>
                      ))}
                    </div>

                  </div>

                </div>
              );
            })}

          </div>

        </div>

        {/* ================= BOTTOM STATEMENT ================= */}



      </div>
    </section>
  );
};

export default HowItWorks;