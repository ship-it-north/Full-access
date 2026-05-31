import { useRef } from 'react'
import { motion, useInView } from 'framer-motion'
import { useCountUp } from '../hooks/useCountUp'

const stats = [
  { value: 47,    suffix: '+',  label: 'Clients Automated',  color: '#00d4ff', desc: 'Dental clinics and businesses fully live' },
  { value: 10000, suffix: '+',  label: 'Hours Saved',        color: '#7b2fff', desc: 'Across all active clients per year' },
  { value: 3,     suffix: 'x',  label: 'Average ROI',        color: '#00d4ff', desc: 'Return on automation investment' },
  { value: 98,    suffix: '%',  label: 'Client Retention',   color: '#7b2fff', desc: 'Clients who renew and expand' },
]

const testimonials = [
  {
    quote: "We went from 12 missed calls a week to zero. The AI books everything now and our front desk actually has time to focus on patients.",
    name: 'Dr. Sophie Tremblay',
    role: 'Dental Clinic Owner, Montréal',
    avatar: 'ST',
    color: '#00d4ff',
  },
  {
    quote: "I didn't believe automation could actually work for a small business. Three months in and we've saved over $8,000 in admin costs.",
    name: 'Marc-André Beaudin',
    role: 'CEO, Service Company, Québec',
    avatar: 'MB',
    color: '#7b2fff',
  },
  {
    quote: "The follow-up system alone reactivated 23 lapsed patients in the first month. That's revenue we were just leaving on the table.",
    name: 'Dr. Kevin Lavoie',
    role: 'Orthodontist, Laval',
    avatar: 'KL',
    color: '#00d4ff',
  },
]

function StatCounter({ stat, start }) {
  const count = useCountUp(stat.value, 2000, start)
  const display = stat.value >= 1000 ? count.toLocaleString() : count

  return (
    <div className="text-center">
      <div
        className="text-5xl lg:text-6xl font-black mb-2 tabular-nums"
        style={{ color: stat.color, textShadow: `0 0 40px ${stat.color}50` }}
      >
        {display}{stat.suffix}
      </div>
      <div className="text-white font-bold text-base mb-1">{stat.label}</div>
      <div className="text-white/35 text-sm">{stat.desc}</div>
    </div>
  )
}

export default function Results() {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })

  return (
    <section id="results" className="relative py-28 bg-[#0a0a0f] overflow-hidden">
      {/* Grid texture */}
      <div
        className="absolute inset-0 opacity-[0.025] pointer-events-none"
        style={{
          backgroundImage: 'linear-gradient(rgba(123,47,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(123,47,255,1) 1px, transparent 1px)',
          backgroundSize: '80px 80px',
        }}
      />

      <div className="container-custom relative z-10">
        {/* Header */}
        <motion.div
          ref={ref}
          initial={{ opacity: 0, y: 30 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8 }}
          className="text-center mb-20"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[#7b2fff]/30 bg-[#7b2fff]/8 mb-6">
            <span className="w-2 h-2 rounded-full bg-[#7b2fff] animate-pulse" />
            <span className="text-[#7b2fff] text-sm font-semibold tracking-wide">Real Results</span>
          </div>

          <h2 className="text-4xl lg:text-5xl font-black text-white mb-5">
            Numbers Don't{' '}
            <span className="text-gradient">Lie</span>
          </h2>
          <p className="text-white/50 text-lg max-w-xl mx-auto">
            Every metric below comes from live client deployments. No projections. No estimates.
          </p>
        </motion.div>

        {/* Stats grid */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="grid grid-cols-2 lg:grid-cols-4 gap-10 mb-24 glass rounded-3xl p-10"
        >
          {stats.map((stat, i) => (
            <StatCounter key={i} stat={stat} start={inView} />
          ))}
        </motion.div>

        {/* Testimonials */}
        <div className="grid md:grid-cols-3 gap-6">
          {testimonials.map((t, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 40 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.6, delay: i * 0.15 }}
              className="relative glass rounded-2xl p-7 group"
            >
              {/* Quote mark */}
              <div
                className="text-6xl font-black leading-none mb-4 opacity-20"
                style={{ color: t.color }}
              >
                "
              </div>

              <p className="text-white/70 text-sm leading-relaxed mb-6 italic">
                "{t.quote}"
              </p>

              {/* Author */}
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center text-xs font-black text-white flex-shrink-0"
                  style={{ background: `linear-gradient(135deg, ${t.color}, ${t.color}88)` }}
                >
                  {t.avatar}
                </div>
                <div>
                  <div className="text-white font-bold text-sm">{t.name}</div>
                  <div className="text-white/35 text-xs">{t.role}</div>
                </div>
              </div>

              {/* Bottom accent */}
              <div
                className="absolute bottom-0 left-7 right-7 h-px opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                style={{ background: `linear-gradient(to right, transparent, ${t.color}, transparent)` }}
              />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
