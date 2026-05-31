import { useCallback, useEffect, useState } from 'react'
import Particles, { initParticlesEngine } from '@tsparticles/react'
import { loadSlim } from '@tsparticles/slim'

export default function ParticleField() {
  const [init, setInit] = useState(false)

  useEffect(() => {
    initParticlesEngine(async (engine) => {
      await loadSlim(engine)
    }).then(() => setInit(true))
  }, [])

  const particlesLoaded = useCallback(() => {}, [])

  const options = {
    background:  { color: { value: 'transparent' } },
    fpsLimit:    60,
    interactivity: {
      events: {
        onHover: { enable: true, mode: 'repulse' },
        resize:  true,
      },
      modes: { repulse: { distance: 80, duration: 0.4 } },
    },
    particles: {
      number:  { value: 60, density: { enable: true, area: 900 } },
      color:   { value: ['#00d4ff', '#7b2fff', '#ffffff'] },
      opacity: { value: { min: 0.1, max: 0.4 }, animation: { enable: true, speed: 0.5 } },
      size:    { value: { min: 1, max: 2.5 } },
      move:    { enable: true, speed: 0.4, direction: 'none', random: true, outModes: 'out' },
      links: {
        enable:   true,
        distance: 160,
        color:    '#00d4ff',
        opacity:  0.08,
        width:    1,
      },
    },
    detectRetina: true,
  }

  if (!init) return null

  return (
    <Particles
      id="tsparticles"
      className="absolute inset-0 w-full h-full"
      particlesLoaded={particlesLoaded}
      options={options}
    />
  )
}
