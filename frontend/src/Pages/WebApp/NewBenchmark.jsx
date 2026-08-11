import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FaArrowLeft,
  FaArrowRight,
  FaServer,
  FaCloudUploadAlt,
  FaRobot,
  FaBullseye,
  FaCheck,
} from "react-icons/fa";

const NewBenchmark = () => {
  const navigate = useNavigate();

  const [step, setStep] = useState(1);

  const [environment, setEnvironment] = useState("");
  const [agent, setAgent] = useState("");
  const [objective, setObjective] = useState("");

  const steps = [
    "Environment",
    "Agent",
    "Objective",
    "Review",
  ];

  const nextStep = () => {
    if (step < 4) {
      setStep(step + 1);
    }
  };

  const previousStep = () => {
    if (step > 1) {
      setStep(step - 1);
    }
  };

  return (
    <div className="min-h-screen bg-[#020817] text-white">

      {/* Sidebar */}
      <div className="fixed left-0 top-0 h-screen w-60">
        {/* Sidebar is already handled by Dashboard layout later */}
      </div>

      {/* Main Content */}
      <main className="ml-60 min-h-screen">

        {/* Top Bar */}
        <div className="h-[74px] border-b border-[#1B2942] bg-[#070D18]" />

        <div className="mx-auto max-w-6xl px-10 py-10">

          {/* Header */}
          <div className="mb-10">

            <button
              onClick={() => navigate("/app")}
              className="mb-5 flex items-center gap-2 text-sm text-[#8190AD] transition hover:text-white"
            >
              <FaArrowLeft size={12} />
              Back to Dashboard
            </button>

            <p className="mb-2 text-sm text-[#9B7BFF]">
              Ariadne Web App
            </p>

            <h1 className="text-3xl font-bold">
              New Benchmark Run
            </h1>

            <p className="mt-2 text-[#8190AD]">
              Configure your environment and agent to start an evaluation.
            </p>

          </div>


          {/* Step Indicator */}
          <div className="mb-10 flex items-center">

            {steps.map((item, index) => {

              const number = index + 1;

              const active = step === number;
              const completed = step > number;

              return (
                <div
                  key={item}
                  className="flex flex-1 items-center"
                >

                  <div className="flex items-center gap-3">

                    <div
                      className={`flex h-9 w-9 items-center justify-center rounded-full border text-sm font-semibold ${
                        completed
                          ? "border-[#6D4AFF] bg-[#6D4AFF] text-white"
                          : active
                          ? "border-[#8B6CFF] bg-[#29145F] text-white"
                          : "border-[#263652] bg-[#0A1220] text-[#66758F]"
                      }`}
                    >
                      {completed ? (
                        <FaCheck size={12} />
                      ) : (
                        number
                      )}
                    </div>

                    <span
                      className={`text-sm ${
                        active || completed
                          ? "text-white"
                          : "text-[#66758F]"
                      }`}
                    >
                      {item}
                    </span>

                  </div>

                  {index < steps.length - 1 && (
                    <div className="mx-5 h-px flex-1 bg-[#1B2942]" />
                  )}

                </div>
              );
            })}

          </div>


          {/* Main Card */}
          <div className="rounded-xl border border-[#1B2942] bg-[#070D18] p-8">


            {/* STEP 1 */}
            {step === 1 && (
              <div>

                <div className="mb-8">

                  <h2 className="text-xl font-semibold">
                    Select Environment
                  </h2>

                  <p className="mt-2 text-sm text-[#8190AD]">
                    Choose the Active Directory environment for this benchmark.
                  </p>

                </div>


                <div className="mb-8 grid grid-cols-2 gap-5">

                  {/* Synthetic */}
                  <button
                    onClick={() => setEnvironment("synthetic")}
                    className={`rounded-xl border p-6 text-left transition ${
                      environment === "synthetic"
                        ? "border-[#7655FF] bg-[#16102F]"
                        : "border-[#24334D] bg-[#0A1220] hover:border-[#4B3B7D]"
                    }`}
                  >

                    <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-lg bg-[#29145F] text-[#9B7BFF]">
                      <FaServer />
                    </div>

                    <h3 className="font-semibold">
                      Synthetic Environment
                    </h3>

                    <p className="mt-2 text-sm leading-6 text-[#8190AD]">
                      Use a pre-built synthetic Active Directory environment
                      generated for Ariadne evaluation.
                    </p>

                  </button>


                  {/* Upload */}
                  <button
                    onClick={() => setEnvironment("upload")}
                    className={`rounded-xl border p-6 text-left transition ${
                      environment === "upload"
                        ? "border-[#7655FF] bg-[#16102F]"
                        : "border-[#24334D] bg-[#0A1220] hover:border-[#4B3B7D]"
                    }`}
                  >

                    <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-lg bg-[#102B43] text-[#50B8FF]">
                      <FaCloudUploadAlt />
                    </div>

                    <h3 className="font-semibold">
                      Upload BloodHound ZIP
                    </h3>

                    <p className="mt-2 text-sm leading-6 text-[#8190AD]">
                      Upload your own BloodHound data and evaluate the agent
                      against your environment.
                    </p>

                  </button>

                </div>


                {/* Available Environments */}
                {environment === "synthetic" && (
                  <div>

                    <h3 className="mb-4 text-sm font-semibold text-white">
                      Available Environments
                    </h3>

                    <div className="space-y-3">

                      {[
                        ["Corporate AD v2", "Large synthetic environment", "1,248", "3,726"],
                        ["Corporate AD v1", "Medium synthetic environment", "892", "2,103"],
                        ["Lab AD", "Small synthetic environment", "312", "645"],
                      ].map((env) => (

                        <button
                          key={env[0]}
                          className="flex w-full items-center justify-between rounded-lg border border-[#1F2E48] bg-[#0A1220] p-4 text-left transition hover:border-[#5A46A5]"
                        >

                          <div>
                            <p className="text-sm font-medium">
                              {env[0]}
                            </p>

                            <p className="mt-1 text-xs text-[#71809D]">
                              {env[1]}
                            </p>
                          </div>

                          <div className="text-right text-xs text-[#71809D]">
                            <p>Nodes: {env[2]}</p>
                            <p>Edges: {env[3]}</p>
                          </div>

                        </button>

                      ))}

                    </div>

                  </div>
                )}

              </div>
            )}


            {/* STEP 2 */}
            {step === 2 && (
              <div>

                <div className="mb-8">

                  <h2 className="text-xl font-semibold">
                    Select Agent
                  </h2>

                  <p className="mt-2 text-sm text-[#8190AD]">
                    Choose the LLM agent that will investigate the environment.
                  </p>

                </div>


                <button
                  onClick={() => setAgent("gemini-flash")}
                  className={`w-full rounded-xl border p-6 text-left transition ${
                    agent === "gemini-flash"
                      ? "border-[#7655FF] bg-[#16102F]"
                      : "border-[#24334D] bg-[#0A1220] hover:border-[#4B3B7D]"
                  }`}
                >

                  <div className="flex items-center gap-5">

                    <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-[#29145F] text-[#9B7BFF]">
                      <FaRobot />
                    </div>

                    <div>

                      <h3 className="font-semibold">
                        Gemini Flash
                      </h3>

                      <p className="mt-1 text-sm text-[#8190AD]">
                        Ariadne LLM agent configured for Active Directory
                        attack-path reasoning.
                      </p>

                    </div>

                  </div>

                </button>

              </div>
            )}


            {/* STEP 3 */}
            {step === 3 && (
              <div>

                <div className="mb-8">

                  <h2 className="text-xl font-semibold">
                    Define Objective
                  </h2>

                  <p className="mt-2 text-sm text-[#8190AD]">
                    Tell Ariadne what the agent should attempt to achieve.
                  </p>

                </div>


                <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-lg bg-[#29145F] text-[#9B7BFF]">
                  <FaBullseye />
                </div>


                <label className="mb-3 block text-sm font-medium">
                  Benchmark Objective
                </label>

                <textarea
                  value={objective}
                  onChange={(e) => setObjective(e.target.value)}
                  placeholder="Example: Find a valid attack path from a low-privileged user to Domain Admin..."
                  className="h-40 w-full resize-none rounded-lg border border-[#24334D] bg-[#0A1220] p-4 text-sm text-white outline-none transition placeholder:text-[#50617C] focus:border-[#7655FF]"
                />

              </div>
            )}


            {/* STEP 4 */}
            {step === 4 && (
              <div>

                <div className="mb-8">

                  <h2 className="text-xl font-semibold">
                    Review Benchmark
                  </h2>

                  <p className="mt-2 text-sm text-[#8190AD]">
                    Review your configuration before starting the benchmark.
                  </p>

                </div>


                <div className="space-y-4">

                  <div className="rounded-lg border border-[#1F2E48] bg-[#0A1220] p-5">

                    <p className="text-xs uppercase tracking-wide text-[#66758F]">
                      Environment
                    </p>

                    <p className="mt-2 text-sm">
                      {environment || "Not selected"}
                    </p>

                  </div>


                  <div className="rounded-lg border border-[#1F2E48] bg-[#0A1220] p-5">

                    <p className="text-xs uppercase tracking-wide text-[#66758F]">
                      Agent
                    </p>

                    <p className="mt-2 text-sm">
                      {agent || "Not selected"}
                    </p>

                  </div>


                  <div className="rounded-lg border border-[#1F2E48] bg-[#0A1220] p-5">

                    <p className="text-xs uppercase tracking-wide text-[#66758F]">
                      Objective
                    </p>

                    <p className="mt-2 text-sm text-[#AAB6CA]">
                      {objective || "No objective provided"}
                    </p>

                  </div>

                </div>

              </div>
            )}


            {/* Footer Buttons */}
            <div className="mt-10 flex items-center justify-between border-t border-[#1B2942] pt-6">

              <button
                onClick={previousStep}
                disabled={step === 1}
                className="flex items-center gap-2 rounded-lg border border-[#24334D] px-5 py-2.5 text-sm text-[#9BA9C2] transition hover:bg-[#101A2D] hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
              >
                <FaArrowLeft size={11} />
                Previous
              </button>


              {step < 4 ? (

                <button
                  onClick={nextStep}
                  className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-[#6D4AFF] to-[#825CFF] px-6 py-2.5 text-sm font-semibold text-white shadow-[0_0_20px_rgba(109,74,255,0.25)] transition hover:brightness-110"
                >
                  Next
                  <FaArrowRight size={11} />
                </button>

              ) : (

                <button
                  onClick={() => navigate("/app/runs")}
                  className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-[#6D4AFF] to-[#825CFF] px-6 py-2.5 text-sm font-semibold text-white shadow-[0_0_20px_rgba(109,74,255,0.25)] transition hover:brightness-110"
                >
                  Start Benchmark
                  <FaArrowRight size={11} />
                </button>

              )}

            </div>

          </div>

        </div>

      </main>

    </div>
  );
};

export default NewBenchmark;