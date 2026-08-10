import HeroSection from "../components/LandingPage/HeroSection";
import HowItWorks from "../components/LandingPage/HowItWorks";
import Features from "../components/LandingPage/Features";
import Footer from "../components/LandingPage/Footer";

function LandingPage() {
  return (
    <div className="min-h-screen bg-[#020817] text-white">

      <main>
        <HeroSection />
        <HowItWorks />
        <Features />

        <Footer />
      </main>
    </div>
  );
}

export default LandingPage;