import { useState, useRef } from 'react'
import { motion, useInView, AnimatePresence } from 'framer-motion'

const services = [
  {
    icon: '📅',
    title: 'AI Appointment Booking Automation',
    tagline: 'Fill your calendar on autopilot',
    color: '#00d4ff',
    description:
      'An intelligent booking system that handles scheduling, confirmations, and reminders 24/7 — without a receptionist. Patients book through SMS, webchat, or voice, and your calendar fills itself.',
    features: ['24/7 automated scheduling', 'SMS & voice booking flows', 'Instant confirmations', 'No-show prevention reminders'],
  },
  {
    icon: '🔄',
    title: 'Patient Follow-Up & Reactivation',
    tagline: 'Win back lapsed patients automatically',
    color: '#7b2fff',
    description:
      'Automated sequences that re-engage inactive patients, follow up post-appointment, request reviews, and nurture long-term loyalty — all personalized and hands-free.',
    features: ['Automated reactivation campaigns', 'Post-visit follow-up sequences', 'Review request automation', 'Loyalty & recall reminders'],
  },
  {
    icon: '💬',
    title: 'AI Chatbots for Lead Capture',
    tagline: 'Convert visitors into booked appointments',
    color: '#00d4ff',
    description:
      'A trained AI assistant on your website and social profiles that answers questions, qualifies leads, and books consultations — capturing revenue that would otherwise slip away.',
    features: ['Trained on your services', 'Multi-platform deployment', 'Lead qualification logic', 'Direct CRM integration'],
  },
  {
    icon: '⚙️',
    title: 'Business Process Automation',
    tagline: 'Eliminate repetitive operational work',
    color: '#7b2fff',
    description:
      'We map your manual workflows and replace them with intelligent automations — from intake forms and insurance verification to internal reporting and staff notifications.',
    features: ['Workflow audit & mapping', 'Custom automation builds', 'System integrations', 'Staff time savings tracking'],
  },
]

function ServiceCard({ service, index }) {
  const [expanded, setExpanded] = useState(false)
  const ref = useRef(null)

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ duration: 0.6, delay: index * 0.12 }}
      animate={{ y: expanded ? 0 : [0, -4, 0] }}
      className="relative glass rounded-2xl p-7 cursor-pointer group overflow-hidden"
      onClick={() => setExpanded(e => !e)}
      style={{
        animationDuration: `${3 + index * 0.5}s`,
        animationTimingFunction: 'ease-in-out',
        animationIterationCount: 'infinite',
      }}
    >
      {/* Hover glow */}
      <div
        className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{ boxShadow: `0 0 50px ${service.color}20, inset 0 0 50px ${service.color}05` }}
      />

      {/* Top row */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div
          className="w-14 h-14 rounded-xl flex items-center justify-center text-2xl flex-shrink-0"
          style={{ background: `${service.color}15`, border: `1px solid ${service.color}30` }}
        >
          {service.icon}
        </div>
        <motion.div
          animate={{ rotate: expanded ? 45 : 0 }}
          transition={{ duration: 0.3 }}
          className="w-8 h-8 rounded-full border border-white/15 flex items-center justify-center text-white/40 flex-shrink-0 mt-1"
        >
          +
        </motion.div>
      </div>

      {/* Title */}
      <h3 className="text-xl font-bold text-white mb-1 leading-snug">{service.title}</h3>
      <p className="text-sm font-medium mb-4" style={{ color: service.color }}>{service.tagline}</p>

      {/* Expanded content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.35 }}
            className="overflow-hidden"
          >
            <p className="text-white/55 text-sm leading-relaxed mb-5">{service.description}</p>
            <ul className="space-y-2">
              {service.features.map((f, i) => (
                <li key={i} className="flex items-center gap-2.5 text-sm text-white/70">
                  <span
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ background: service.color, boxShadow: `0 0 6px ${service.color}` }}
                  />
                  {f}
                </li>
              ))}
            </ul>
            <div className="mt-6">
              <a
                href="#contact"
                onClick={e => e.stopPropagation()}
                className="inline-flex items-center gap-2 text-sm font-bold transition-all"
                style={{ color: service.color }}
              >
                Get this service →
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bottom border glow */}
      <div
        className="absolute bottom-0 left-0 right-0 h-px"
        style={{ background: `linear-gradient(to right, transparent, ${service.color}40, transparent)` }}
      />
    </motion.div>
  )
}

export default function Services() {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })

  return (
    <section id="services" className="relative py-28 overflow-hidden" style={{ background: 'linear-gradient(180deg, #0a0a0f 0%, #0d0d18 50%, #0a0a0f 100%)' }}>
      {/* Ambient orbs */}
      <div className="absolute top-0 left-0 w-96 h-96 rounded-full bg-[#00d4ff]/5 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-96 h-96 rounded-full bg-[#7b2fff]/6 blur-[120px] pointer-events-none" />

      <div className="container-custom relative z-10">
        {/* Header */}
        <motion.div
          ref={ref}
          initial={{ opacity: 0, y: 30 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[#00d4ff]/30 bg-[#00d4ff]/8 mb-6">
            <span className="w-2 h-2 rounded-full bg-[#00d4ff] animate-pulse" />
            <span className="text-[#00d4ff] text-sm font-semibold tracking-wide">What We Build</span>
          </div>

          <h2 className="text-4xl lg:text-5xl font-black text-white mb-5">
            AI Systems That{' '}
            <span className="text-gradient">Run Your Growth</span>
          </h2>
          <p className="text-white/50 text-lg max-w-2xl mx-auto leading-relaxed">
            Click any card to see what's inside. Every system is custom-built for your clinic or business —
            no templates, no generic software.
          </p>
        </motion.div>

        {/* Grid */}
        <div className="grid md:grid-cols-2 gap-6">
          {services.map((s, i) => (
            <ServiceCard key={i} service={s} index={i} />
          ))}
        </div>

        {/* Bottom CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7, delay: 0.4 }}
          className="text-center mt-14"
        >
          <p className="text-white/40 text-sm mb-4">Not sure which system you need?</p>
          <a
            href="#contact"
            className="inline-flex items-center gap-3 px-8 py-4 rounded-xl font-bold text-white
                       bg-gradient-to-r from-[#00d4ff] to-[#7b2fff]
                       hover:shadow-[0_0_35px_rgba(0,212,255,0.4)] transition-all"
          >
            Get a Free Audit →
          </a>
        </motion.div>
      </div>
    </section>
  )
}
