import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import MagneticButton from './MagneticButton'
import ParticleField  from './ParticleField'
import ThreeScene     from './ThreeScene'

const PHRASES = ['Automate Your Clinic', 'Convert More Patients', 'Scale Without Hiring']

export default function Hero() {
  const [displayText,  setDisplayText]  = useState('')
  const [phraseIndex,  setPhraseIndex]  = useState(0)
  const [charIndex,    setCharIndex]    = useState(0)
  const [isDeleting,   setIsDeleting]   = useState(false)
  const [isPaused,     setIsPaused]     = useState(false)

  useEffect(() => {
    if (isPaused) return
    const phrase = PHRASES[phraseIndex]

    if (!isDeleting && charIndex === phrase.length) {
      setIsPaused(true)
      const t = setTimeout(() => { setIsDeleting(true); setIsPaused(false) }, 2200)
      return () => clearTimeout(t)
    }

    if (isDeleting && charIndex === 0) {
      setIsDeleting(false)
      setPhraseIndex(i => (i + 1) % PHRASES.length)
      return
    }

    const delay = isDeleting ? 45 : 95
    const t = setTimeout(() => {
      const next = charIndex + (isDeleting ? -1 : 1)
      setCharIndex(next)
      setDisplayText(phrase.substring(0, next))
    }, delay)
    return () => clearTimeout(t)
  }, [charIndex, isDeleting, phraseIndex, isPaused])

  return (
    <section className="relative min-h-screen flex items-center overflow-hidden bg-[#0a0a0f]">

      {/* Particle background */}
      <div className="absolute inset-0 z-0">
        <ParticleField />
      </div>

      {/* Ambient glow orbs */}
      <div className="absolute top-24 left-16 w-72 h-72 rounded-full bg-[#7b2fff]/12 blur-[100px] animate-float pointer-events-none" />
      <div className="absolute bottom-24 right-16 w-96 h-96 rounded-full bg-[#00d4ff]/10 blur-[120px] animate-float-slow pointer-events-none" style={{ animationDelay: '1.5s' }} />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] rounded-full bg-[#7b2fff]/5 blur-[80px] pointer-events-none" />

      <div className="container-custom relative z-10 w-full">
        <div className="grid lg:grid-cols-2 gap-16 items-center min-h-screen py-28">

          {/* ── Left ── */}
          <div>
            <motion.div
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.9, ease: 'easeOut' }}
            >
              {/* Badge */}
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.6, delay: 0.2 }}
                className="inline-flex items-center gap-2.5 px-4 py-2 rounded-full
                           border border-[#00d4ff]/30 bg-[#00d4ff]/8 mb-8"
              >
                <span className="w-2 h-2 rounded-full bg-[#00d4ff] animate-pulse shadow-[0_0_8px_#00d4ff]" />
                <span className="text-[#00d4ff] text-sm font-semibold tracking-wide">
                  AI Automation · Dental & Business
                </span>
              </motion.div>

              {/* Headline */}
              <motion.h1
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8, delay: 0.3 }}
                className="text-5xl lg:text-[4.5rem] font-black leading-[1.05] tracking-tight mb-6 text-white"
              >
                The Future of Your{' '}
                <span className="text-gradient">Practice</span>
                <br />Starts Here
              </motion.h1>

              {/* Typing */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6 }}
                className="h-12 flex items-center mb-6"
              >
                <span className="text-2xl font-semibold text-white/50">We help you </span>
                <span className="text-2xl font-bold text-[#00d4ff] ml-2">
                  {displayText}
                  <span className="animate-pulse text-[#00d4ff]/80">|</span>
                </span>
              </motion.div>

              {/* Subtext */}
              <motion.p
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.7 }}
                className="text-lg text-white/55 leading-relaxed mb-10 max-w-[520px]"
              >
                We build AI-powered automation systems for dental clinics and growing businesses.
                Cut costs, reclaim hours, and grow — without hiring a single extra person.
              </motion.p>

              {/* CTAs */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.85 }}
                className="flex flex-wrap gap-4 mb-12"
              >
                <MagneticButton
                  href="#contact"
                  className="px-8 py-4 rounded-xl font-bold text-lg text-white
                             bg-gradient-to-r from-[#00d4ff] to-[#7b2fff]
                             hover:shadow-[0_0_35px_rgba(0,212,255,0.45)] transition-all"
                >
                  Book a Free Call →
                </MagneticButton>
                <MagneticButton
                  href="#services"
                  className="px-8 py-4 rounded-xl font-bold text-lg text-white
                             glass border border-white/15
                             hover:border-[#00d4ff]/40 hover:bg-white/8 transition-all"
                >
                  See Our Services
                </MagneticButton>
              </motion.div>

              {/* Social proof row */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1 }}
                className="flex flex-wrap items-center gap-6 text-sm"
              >
                {[
                  { num: '47+',  label: 'Clients Automated' },
                  { num: '10K+', label: 'Hours Saved'       },
                  { num: '3x',   label: 'Average ROI'       },
                ].map(({ num, label }, i) => (
                  <div key={i} className="flex items-center gap-2.5">
                    {i > 0 && <div className="w-px h-4 bg-white/15" />}
                    <span className="font-black text-[#00d4ff] text-base">{num}</span>
                    <span className="text-white/40">{label}</span>
                  </div>
                ))}
              </motion.div>
            </motion.div>
          </div>

          {/* ── Right: Three.js ── */}
          <motion.div
            className="hidden lg:block relative h-[600px]"
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1.1, delay: 0.4 }}
          >
            <ThreeScene />
          </motion.div>
        </div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-white/25 text-xs font-medium tracking-widest uppercase"
        animate={{ y: [0, 7, 0] }}
        transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
      >
        <span>Scroll</span>
        <div className="w-px h-10 bg-gradient-to-b from-white/25 to-transparent" />
      </motion.div>
    </section>
  )
}
