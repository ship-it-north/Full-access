import { useRef, useState } from 'react'
import { motion, useInView } from 'framer-motion'
import MagneticButton from './MagneticButton'

const FORMSPREE = 'https://formspree.io/f/mdajebpz'

export default function Contact() {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })

  const [form, setForm] = useState({ name: '', email: '', company: '', message: '' })
  const [status, setStatus] = useState('idle') // idle | sending | success | error

  const handleChange = (e) => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setStatus('sending')
    try {
      const res = await fetch(FORMSPREE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(form),
      })
      if (res.ok) {
        setStatus('success')
        setForm({ name: '', email: '', company: '', message: '' })
      } else {
        setStatus('error')
      }
    } catch {
      setStatus('error')
    }
  }

  return (
    <section id="contact" className="relative py-28 overflow-hidden" style={{ background: 'linear-gradient(180deg, #0a0a0f 0%, #0d0d1a 100%)' }}>
      {/* Ambient glows */}
      <div className="absolute bottom-0 left-1/4 w-[500px] h-[300px] rounded-full bg-[#00d4ff]/5 blur-[120px] pointer-events-none" />
      <div className="absolute top-0 right-1/4 w-[400px] h-[300px] rounded-full bg-[#7b2fff]/6 blur-[100px] pointer-events-none" />

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
            <span className="text-[#00d4ff] text-sm font-semibold tracking-wide">Book a Free Strategy Call</span>
          </div>

          <h2 className="text-4xl lg:text-5xl font-black text-white mb-5">
            Let's Build Your{' '}
            <span className="text-gradient">AI System</span>
          </h2>
          <p className="text-white/50 text-lg max-w-xl mx-auto">
            30-minute call. No pitch. Just a clear breakdown of what AI automation can do for your specific business.
          </p>
        </motion.div>

        <div className="grid lg:grid-cols-2 gap-10 items-start max-w-5xl mx-auto">
          {/* Form */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            animate={inView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.8, delay: 0.2 }}
          >
            <div className="animated-border rounded-2xl p-px">
              <div className="glass rounded-2xl p-8">
                {status === 'success' ? (
                  <div className="text-center py-10">
                    <div className="text-5xl mb-4">🎉</div>
                    <h3 className="text-2xl font-black text-white mb-2">You're In</h3>
                    <p className="text-white/55">
                      We'll reach out within 24 hours to book your strategy call.
                    </p>
                  </div>
                ) : (
                  <form onSubmit={handleSubmit} className="space-y-5">
                    <div>
                      <label className="block text-white/60 text-sm font-medium mb-2">Full Name *</label>
                      <input
                        name="name"
                        value={form.name}
                        onChange={handleChange}
                        required
                        placeholder="Dr. Sophie Tremblay"
                        className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/25
                                   focus:outline-none focus:border-[#00d4ff]/50 focus:bg-white/8 transition-all text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-white/60 text-sm font-medium mb-2">Email Address *</label>
                      <input
                        name="email"
                        type="email"
                        value={form.email}
                        onChange={handleChange}
                        required
                        placeholder="you@yourclinic.com"
                        className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/25
                                   focus:outline-none focus:border-[#00d4ff]/50 focus:bg-white/8 transition-all text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-white/60 text-sm font-medium mb-2">
                        Business / Clinic Name <span className="text-white/30">(optional)</span>
                      </label>
                      <input
                        name="company"
                        value={form.company}
                        onChange={handleChange}
                        placeholder="Clinique Tremblay"
                        className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/25
                                   focus:outline-none focus:border-[#00d4ff]/50 focus:bg-white/8 transition-all text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-white/60 text-sm font-medium mb-2">
                        What's your biggest challenge? <span className="text-white/30">(optional)</span>
                      </label>
                      <textarea
                        name="message"
                        value={form.message}
                        onChange={handleChange}
                        rows={3}
                        placeholder="e.g. We miss too many calls, our follow-up is inconsistent..."
                        className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/25
                                   focus:outline-none focus:border-[#00d4ff]/50 focus:bg-white/8 transition-all text-sm resize-none"
                      />
                    </div>

                    {status === 'error' && (
                      <p className="text-red-400 text-sm">Something went wrong. Please try again or email us directly.</p>
                    )}

                    <MagneticButton
                      type="submit"
                      className={`w-full py-4 rounded-xl font-bold text-lg text-white transition-all
                                  bg-gradient-to-r from-[#00d4ff] to-[#7b2fff]
                                  hover:shadow-[0_0_35px_rgba(0,212,255,0.4)]
                                  ${status === 'sending' ? 'opacity-60 cursor-wait' : ''}`}
                    >
                      {status === 'sending' ? 'Sending…' : 'Book My Free Strategy Call →'}
                    </MagneticButton>

                    <p className="text-white/25 text-xs text-center">
                      No spam. No pressure. Just clarity on what's possible.
                    </p>
                  </form>
                )}
              </div>
            </div>
          </motion.div>

          {/* Right side info */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            animate={inView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.8, delay: 0.3 }}
            className="space-y-6"
          >
            {[
              { icon: '🕐', title: '30-Minute Call', body: 'No fluff. We come prepared with ideas specific to your industry and business size.' },
              { icon: '🔍', title: 'Free Automation Audit', body: 'We map your current workflow and show you exactly which tasks can be automated and what it saves you.' },
              { icon: '📈', title: 'Custom Roadmap', body: "You leave with a clear plan — even if you don't work with us. That's how confident we are in the value." },
            ].map((item, i) => (
              <div key={i} className="flex gap-4 glass rounded-xl p-5 group hover:border-[#00d4ff]/20 transition-colors">
                <div className="text-2xl flex-shrink-0 mt-0.5">{item.icon}</div>
                <div>
                  <h4 className="text-white font-bold mb-1">{item.title}</h4>
                  <p className="text-white/45 text-sm leading-relaxed">{item.body}</p>
                </div>
              </div>
            ))}

            {/* Direct contact */}
            <div className="glass rounded-xl p-5 border border-[#00d4ff]/10">
              <p className="text-white/40 text-xs font-medium uppercase tracking-wider mb-3">Prefer to reach out directly?</p>
              <a
                href="mailto:info@fyltrmedia.com"
                className="text-[#00d4ff] font-semibold hover:underline text-sm"
              >
                info@fyltrmedia.com
              </a>
              <p className="text-white/30 text-xs mt-1">We respond within 24 hours.</p>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
