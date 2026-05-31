import { useRef, useState } from 'react'
import { motion } from 'framer-motion'

export default function MagneticButton({ children, className = '', href, onClick, type = 'button' }) {
  const ref = useRef(null)
  const [pos, setPos] = useState({ x: 0, y: 0 })

  const handleMouseMove = (e) => {
    const rect = ref.current.getBoundingClientRect()
    const x = (e.clientX - rect.left - rect.width  / 2) * 0.35
    const y = (e.clientY - rect.top  - rect.height / 2) * 0.35
    setPos({ x, y })
  }

  const handleMouseLeave = () => setPos({ x: 0, y: 0 })

  const Tag = href ? 'a' : 'button'

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      animate={{ x: pos.x, y: pos.y }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      className="inline-block"
    >
      <Tag
        href={href}
        onClick={onClick}
        type={href ? undefined : type}
        className={`block cursor-pointer transition-all duration-200 ${className}`}
      >
        {children}
      </Tag>
    </motion.div>
  )
}
