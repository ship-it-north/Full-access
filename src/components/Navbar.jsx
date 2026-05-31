import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import MagneticButton from './MagneticButton'

const links = [
  { label: 'Why AI',   href: '#why'      },
  { label: 'Services', href: '#services' },
  { label: 'Results',  href: '#results'  },
  { label: 'Contact',  href: '#contact'  },
]

export default function Navbar() {
  const [scrolled,    setScrolled]    = useState(false)
  const [mobileOpen,  setMobileOpen]  = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <motion.nav
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0,   opacity: 1 }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled ? 'glass border-b border-white/8 py-3' : 'bg-transparent py-5'
      }`}
    >
      <div className="container-custom flex items-center justify-between">
        {/* Logo */}
        <a href="#" className="font-black text-xl tracking-tight select-none">
          <span className="text-gradient">FYLTR</span>
          <span className="text-white/40 font-light mx-1">|</span>
          <span className="text-white">MEDIA</span>
        </a>

        {/* Desktop links */}
        <div className="hidden md:flex items-center gap-8">
          {links.map(({ label, href }) => (
            <a
              key={href}
              href={href}
              className="text-sm font-medium text-white/60 hover:text-white transition-colors relative group"
            >
              {label}
              <span className="absolute -bottom-1 left-0 w-0 h-px bg-gradient-to-r from-[#00d4ff] to-[#7b2fff] group-hover:w-full transition-all duration-300" />
            </a>
          ))}
        </div>

        {/* CTA */}
        <div className="hidden md:block">
          <MagneticButton
            href="#contact"
            className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-[#00d4ff] to-[#7b2fff] text-white font-bold text-sm
                       hover:shadow-[0_0_25px_rgba(0,212,255,0.4)] transition-all"
          >
            Book Free Call
          </MagneticButton>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden flex flex-col gap-1.5 p-2"
          onClick={() => setMobileOpen(o => !o)}
          aria-label="Toggle menu"
        >
          <span className={`w-6 h-px bg-white transition-all duration-300 ${mobileOpen ? 'rotate-45 translate-y-2' : ''}`} />
          <span className={`w-6 h-px bg-white transition-all duration-300 ${mobileOpen ? 'opacity-0' : ''}`} />
          <span className={`w-6 h-px bg-white transition-all duration-300 ${mobileOpen ? '-rotate-45 -translate-y-2' : ''}`} />
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{    opacity: 0, height: 0 }}
          className="md:hidden glass border-t border-white/8 mt-2"
        >
          <div className="container-custom py-6 flex flex-col gap-4">
            {links.map(({ label, href }) => (
              <a
                key={href}
                href={href}
                onClick={() => setMobileOpen(false)}
                className="text-white/70 hover:text-white font-medium py-2 border-b border-white/5 transition-colors"
              >
                {label}
              </a>
            ))}
            <a
              href="#contact"
              onClick={() => setMobileOpen(false)}
              className="mt-2 px-6 py-3 rounded-lg bg-gradient-to-r from-[#00d4ff] to-[#7b2fff] text-white font-bold text-center"
            >
              Book Free Call
            </a>
          </div>
        </motion.div>
      )}
    </motion.nav>
  )
}
