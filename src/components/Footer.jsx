import { motion } from 'framer-motion'

const links = [
  { label: 'Why AI',   href: '#why'      },
  { label: 'Services', href: '#services' },
  { label: 'Results',  href: '#results'  },
  { label: 'Contact',  href: '#contact'  },
]

export default function Footer() {
  return (
    <footer className="relative bg-[#060609] border-t border-white/5 overflow-hidden">
      {/* Top glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-px bg-gradient-to-r from-transparent via-[#00d4ff]/30 to-transparent" />

      <div className="container-custom py-14">
        <div className="flex flex-col md:flex-row items-center justify-between gap-8">
          {/* Logo */}
          <motion.a
            href="#"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="font-black text-xl tracking-tight select-none"
          >
            <span className="text-gradient">FYLTR</span>
            <span className="text-white/30 font-light mx-1">|</span>
            <span className="text-white">MEDIA</span>
          </motion.a>

          {/* Nav */}
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="flex flex-wrap items-center justify-center gap-6"
          >
            {links.map(({ label, href }) => (
              <a
                key={href}
                href={href}
                className="text-sm text-white/35 hover:text-white/80 transition-colors"
              >
                {label}
              </a>
            ))}
          </motion.div>

          {/* Email */}
          <motion.a
            href="mailto:info@fyltrmedia.com"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="text-sm text-[#00d4ff]/60 hover:text-[#00d4ff] transition-colors"
          >
            info@fyltrmedia.com
          </motion.a>
        </div>

        {/* Divider */}
        <div className="h-px bg-white/5 my-8" />

        {/* Bottom row */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-white/20">
          <span>© {new Date().getFullYear()} FYLTR Media. All rights reserved.</span>
          <span>
            AI Automation Agency · Québec, Canada ·{' '}
            <a href="mailto:info@fyltrmedia.com" className="hover:text-white/50 transition-colors">
              fyltrmedia.com
            </a>
          </span>
        </div>
      </div>
    </footer>
  )
}
