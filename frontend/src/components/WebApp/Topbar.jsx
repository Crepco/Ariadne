const Topbar = () => {
  return (
    <header className="sticky top-0 z-40 h-16 bg-[#020817]/95 backdrop-blur-xl border-b border-[#17233A] flex items-center justify-between px-6">

      <div className="w-96">
        <input
          type="text"
          placeholder="Search runs, environments..."
          className="w-full bg-[#080F20] border border-[#1B2943] rounded-lg px-4 py-2 text-sm text-white placeholder:text-[#596985] outline-none focus:border-[#6D4AFF]"
        />
      </div>



    </header>
  );
};

export default Topbar;