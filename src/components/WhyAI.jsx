import { useRef, useState } from 'react'
import { motion, useInView } from 'framer-motion'

const cards = [
  {
    icon: '⚡',
    stat: '3x',
    title: 'Businesses using AI grow 3x faster',
    body: 'Companies that integrate AI automation outpace competitors across every measurable metric — bookings, revenue, and retention.',
    color: '#00d4ff',
  },
  {
    icon: '🤖',
    stat: '80%',
    title: '80% of repetitive tasks can be automated today',
    body: 'Appointment reminders, follow-ups, lead qualification, intake forms — all running 24/7 without a single employee touching them.',
    color: '#7b2fff',
  },
  {
    icon: '🚀',
    stat: 'Now',
    title: 'Your competitors are already doing it',
    body: 'The window to gain a first-mover advantage in your market is closing fast. The clinics that automate now will own their category.',
    color: '#00d4ff',
  },
]

function TiltCard({ card, index }) {
  const ref = useRef(null)
  const [tilt, setTilt] = useState({ x: 0, y: 0 })
  const [hovered, setHovered] = useState(false)

  const handleMouseMove = (e) => {
    const rect = ref.current.getBoundingClientRect()
    const x = ((e.clientY - rect.top)  / rect.height - 0.5) * -16
    const y = ((e.clientX - rect.left) / rect.width  - 0.5) *  16
    setTilt({ x, y })
  }

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 50 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.7, delay: index * 0.15 }}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setTilt({ x: 0, y: 0 }); setHovered(false) }}
      style={{
        transform: `perspective(800px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
        transition: hovered ? 'transform 0.1s ease' : 'transform 0.5s ease',
      }}
      className="relative glass rounded-2xl p-8 cursor-default group"
    >
      {/* Glow border on hover */}
      <div
        className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{ boxShadow: `0 0 40px ${card.color}25, inset 0 0 40px ${card.color}08` }}
      />

      {/* Icon */}
      <div
        className="w-16 h-16 rounded-xl flex items-center justify-center text-3xl mb-6"
        style={{ background: `${card.color}15`, border: `1px solid ${card.color}30` }}
      >
        {card.icon}
      </div>

      {/* Stat */}
      <div
        className="text-5xl font-black mb-3"
        style={{ color: card.color, textShadow: `0 0 30px ${card.color}60` }}
      >
        {card.stat}
      </div>

      {/* Title */}
      <h3 className="text-xl font-bold text-white mb-3 leading-snug">{card.title}</h3>

      {/* Body */}
      <p className="text-white/50 leading-relaxed text-sm">{card.body}</p>

      {/* Bottom accent line */}
      <div
        className="absolute bottom-0 left-8 right-8 h-px opacity-0 group-hover:opacity-100 transition-opacity duration-500"
        style={{ background: `linear-gradient(to right, transparent, ${card.color}, transparent)` }}
      />
    </motion.div>
  )
}

export default function WhyAI() {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-100px' })

  return (
    <section id="why" className="relative py-28 bg-[#0a0a0f] overflow-hidden">
      {/* Background grid */}
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: 'linear-gradient(rgba(0,212,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,1) 1px, transparent 1px)',
          backgroundSize: '60px 60px',
        }}
      />

      {/* Ambient glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] rounded-full bg-[#7b2fff]/6 blur-[120px] pointer-events-none" />

      <div className="container-custom relative z-10">
        {/* Header */}
        <motion.div
          ref={ref}
          initial={{ opacity: 0, y: 30 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[#7b2fff]/30 bg-[#7b2fff]/8 mb-6">
            <span className="w-2 h-2 rounded-full bg-[#7b2fff] animate-pulse" />
            <span className="text-[#7b2fff] text-sm font-semibold tracking-wide">Why AI, Why Now</span>
          </div>

          <h2 className="text-4xl lg:text-5xl font-black text-white mb-5">
            The AI Shift Is{' '}
            <span className="text-gradient">Already Here</span>
          </h2>
          <p className="text-white/50 text-lg max-w-2xl mx-auto leading-relaxed">
            This isn't a trend. It's a fundamental shift in how successful clinics and businesses operate.
            The question isn't if you should automate — it's how fast.
          </p>
        </motion.div>

        {/* Cards */}
        <div className="grid md:grid-cols-3 gap-6">
          {cards.map((card, i) => (
            <TiltCard key={i} card={card} index={i} />
          ))}
        </div>
      </div>
    </section>
  )
}
