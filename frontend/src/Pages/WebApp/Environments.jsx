import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FaPlus,
  FaSearch,
  FaServer,
  FaUpload,
  FaEllipsisV,
  FaArrowRight,
  FaCheckCircle,
} from "react-icons/fa";

const Environments = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");

  const environments = [
    {
      id: 1,
      name: "Corporate AD v2",
      type: "Synthetic Environment",
      nodes: "1,248",
      edges: "3,726",
      status: "Ready",
    },
    {
      id: 2,
      name: "Corporate AD v1",
      type: "Synthetic Environment",
      nodes: "892",
      edges: "2,103",
      status: "Ready",
    },
    {
      id: 3,
      name: "Lab AD",
      type: "Synthetic Environment",
      nodes: "312",
      edges: "645",
      status: "Ready",
    },
  ];

  const filteredEnvironments = environments.filter((environment) =>
    environment.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-[#020817] text-white">

      <main className="ml-60 min-h-screen">

        {/* Topbar */}
        <div className="flex h-[74px] items-center justify-between border-b border-[#1B2942] bg-[#070D18] px-8">

          <div>
            <h1 className="text-lg font-semibold">
              Environments
            </h1>

            <p className="text-xs text-[#71809D]">
              Manage your benchmark environments
            </p>
          </div>

          <button
            onClick={() => navigate("/app/benchmark")}
            className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-[#6D4AFF] to-[#825CFF] px-4 py-2.5 text-sm font-semibold text-white shadow-[0_0_20px_rgba(109,74,255,0.2)] transition hover:brightness-110"
          >
            <FaPlus size={12} />
            New Environment
          </button>

        </div>


        {/* Content */}
        <div className="p-8">

          {/* Header */}
          <div className="mb-8">

            <h2 className="text-2xl font-bold">
              Your Environments
            </h2>

            <p className="mt-2 text-sm text-[#8190AD]">
              Active Directory environments available for Ariadne benchmarks.
            </p>

          </div>


          {/* Stats */}
          <div className="mb-8 grid grid-cols-3 gap-5">

            <div className="rounded-xl border border-[#1B2942] bg-[#070D18] p-5">

              <p className="text-xs text-[#71809D]">
                Total Environments
              </p>

              <p className="mt-2 text-2xl font-bold">
                {environments.length}
              </p>

            </div>


            <div className="rounded-xl border border-[#1B2942] bg-[#070D18] p-5">

              <p className="text-xs text-[#71809D]">
                Ready
              </p>

              <p className="mt-2 text-2xl font-bold text-[#7CFFB2]">
                {environments.filter((env) => env.status === "Ready").length}
              </p>

            </div>


            <div className="rounded-xl border border-[#1B2942] bg-[#070D18] p-5">

              <p className="text-xs text-[#71809D]">
                Total Nodes
              </p>

              <p className="mt-2 text-2xl font-bold">
                2,452
              </p>

            </div>

          </div>


          {/* Search */}
          <div className="mb-5 flex items-center rounded-lg border border-[#24334D] bg-[#070D18] px-4">

            <FaSearch
              size={13}
              className="text-[#66758F]"
            />

            <input
              type="text"
              placeholder="Search environments..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-transparent px-3 py-3 text-sm text-white outline-none placeholder:text-[#50617C]"
            />

          </div>


          {/* Environment List */}
          <div className="space-y-4">

            {filteredEnvironments.map((environment) => (

              <div
                key={environment.id}
                className="group rounded-xl border border-[#1B2942] bg-[#070D18] p-6 transition hover:border-[#3A3262]"
              >

                <div className="flex items-center justify-between">

                  {/* Left */}
                  <div className="flex items-center gap-5">

                    <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-[#29145F] text-[#9B7BFF]">
                      <FaServer size={18} />
                    </div>

                    <div>

                      <div className="flex items-center gap-3">

                        <h3 className="font-semibold">
                          {environment.name}
                        </h3>

                        <span className="flex items-center gap-1 rounded-full bg-[#0B2A1A] px-2.5 py-1 text-[10px] font-medium text-[#7CFFB2]">
                          <FaCheckCircle size={9} />
                          {environment.status}
                        </span>

                      </div>

                      <p className="mt-1 text-xs text-[#71809D]">
                        {environment.type}
                      </p>

                    </div>

                  </div>


                  {/* Stats */}
                  <div className="hidden items-center gap-12 md:flex">

                    <div>
                      <p className="text-[10px] uppercase tracking-wide text-[#596982]">
                        Nodes
                      </p>

                      <p className="mt-1 text-sm font-medium">
                        {environment.nodes}
                      </p>
                    </div>


                    <div>
                      <p className="text-[10px] uppercase tracking-wide text-[#596982]">
                        Edges
                      </p>

                      <p className="mt-1 text-sm font-medium">
                        {environment.edges}
                      </p>
                    </div>

                  </div>


                  {/* Actions */}
                  <div className="flex items-center gap-3">

                    <button
                      onClick={() =>
                        navigate(`/app/environments/${environment.id}`)
                      }
                      className="flex items-center gap-2 rounded-lg border border-[#293852] px-4 py-2 text-xs text-[#AAB6CA] transition hover:border-[#7655FF] hover:text-white"
                    >
                      View
                      <FaArrowRight size={9} />
                    </button>

                    <button
                      className="flex h-9 w-9 items-center justify-center rounded-lg text-[#66758F] transition hover:bg-[#101A2D] hover:text-white"
                    >
                      <FaEllipsisV size={13} />
                    </button>

                  </div>

                </div>

              </div>

            ))}


            {/* Empty Search */}
            {filteredEnvironments.length === 0 && (

              <div className="rounded-xl border border-dashed border-[#263652] py-16 text-center">

                <FaSearch
                  className="mx-auto mb-4 text-[#44536C]"
                  size={22}
                />

                <p className="text-sm font-medium">
                  No environments found
                </p>

                <p className="mt-1 text-xs text-[#71809D]">
                  Try searching for a different environment.
                </p>

              </div>

            )}

          </div>


          {/* Upload Section */}
          <div className="mt-8 rounded-xl border border-dashed border-[#293852] bg-[#060C18] p-8">

            <div className="flex items-center justify-between">

              <div className="flex items-center gap-4">

                <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#102B43] text-[#50B8FF]">
                  <FaUpload />
                </div>

                <div>

                  <h3 className="text-sm font-semibold">
                    Import a BloodHound Environment
                  </h3>

                  <p className="mt-1 text-xs text-[#71809D]">
                    Upload a BloodHound ZIP to create a benchmark environment.
                  </p>

                </div>

              </div>


              <button
                onClick={() => navigate("/app/benchmark")}
                className="rounded-lg border border-[#30415F] px-4 py-2 text-xs font-medium text-[#AAB6CA] transition hover:border-[#7655FF] hover:text-white"
              >
                Import ZIP
              </button>

            </div>

          </div>

        </div>

      </main>

    </div>
  );
};

export default Environments;