import Navbar    from './components/Navbar'
import Hero      from './components/Hero'
import WhyAI     from './components/WhyAI'
import Services  from './components/Services'
import Results   from './components/Results'
import Contact   from './components/Contact'
import Footer    from './components/Footer'

export default function App() {
  return (
    <main className="bg-[#0a0a0f] text-white overflow-x-hidden">
      <Navbar />
      <Hero />
      <WhyAI />
      <Services />
      <Results />
      <Contact />
      <Footer />
    </main>
  )
}
