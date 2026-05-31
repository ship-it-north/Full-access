import { useState, useEffect, useRef } from 'react'

export function useCountUp(target, duration = 2000, start = false) {
  const [count, setCount] = useState(0)
  const raf   = useRef(null)
  const start_ = useRef(null)

  useEffect(() => {
    if (!start) return
    start_.current = null

    const step = (timestamp) => {
      if (!start_.current) start_.current = timestamp
      const progress = Math.min((timestamp - start_.current) / duration, 1)
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      setCount(Math.floor(eased * target))
      if (progress < 1) raf.current = requestAnimationFrame(step)
    }

    raf.current = requestAnimationFrame(step)
    return () => { if (raf.current) cancelAnimationFrame(raf.current) }
  }, [target, duration, start])

  return count
}
