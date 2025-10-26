import Header from './components/Header';
import HeroSection from './components/HeroSection';
import './index.css';
import heroBg from './assets/images/hero-bg.png';

function App() {
  return (
    <div className="min-h-screen bg-cover bg-no-repeat bg-center bg-fixed text-gray-800 font-sans tracking-normal" 
         style={{ backgroundImage: `url(${heroBg})` }}>
      <Header />
      <HeroSection />
    </div>
  );
}

export default App;