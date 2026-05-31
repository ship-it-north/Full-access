import { useEffect, useRef } from 'react'
import * as THREE from 'three'

export default function ThreeScene() {
  const mountRef = useRef(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    let mounted = true
    const W = mount.clientWidth  || 600
    const H = mount.clientHeight || 600

    // ── Scene
    const scene    = new THREE.Scene()
    const camera   = new THREE.PerspectiveCamera(60, W / H, 0.1, 100)
    camera.position.z = 7

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setSize(W, H)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setClearColor(0x000000, 0)
    mount.appendChild(renderer.domElement)

    // ── Materials
    const matBlue = new THREE.MeshBasicMaterial({
      color: 0x00d4ff, wireframe: true, transparent: true, opacity: 0.55,
    })
    const matPurple = new THREE.MeshBasicMaterial({
      color: 0x7b2fff, wireframe: true, transparent: true, opacity: 0.45,
    })
    const matWhite = new THREE.MeshBasicMaterial({
      color: 0xffffff, wireframe: true, transparent: true, opacity: 0.18,
    })

    // ── Meshes
    const ico   = new THREE.Mesh(new THREE.IcosahedronGeometry(1.3, 0), matBlue)
    ico.position.set(1.8, 0.4, 0)

    const torus = new THREE.Mesh(new THREE.TorusGeometry(1.0, 0.3, 8, 40), matPurple)
    torus.position.set(-2.0, -1.0, -0.5)

    const octa  = new THREE.Mesh(new THREE.OctahedronGeometry(0.7), matWhite)
    octa.position.set(0.3, 2.2, -1.5)

    const tetra = new THREE.Mesh(new THREE.TetrahedronGeometry(0.55), matBlue)
    tetra.position.set(-0.8, -2.5, 0.2)

    const box   = new THREE.Mesh(new THREE.BoxGeometry(0.65, 0.65, 0.65), matPurple)
    box.position.set(3.2, -1.5, -1.2)

    const torus2 = new THREE.Mesh(new THREE.TorusKnotGeometry(0.5, 0.15, 64, 8), matBlue)
    torus2.position.set(-1.5, 1.8, -1)

    scene.add(ico, torus, octa, tetra, box, torus2)

    // ── Mouse parallax
    let mouse = { x: 0, y: 0 }
    const onMouseMove = (e) => {
      mouse.x = (e.clientX / window.innerWidth  - 0.5) * 0.6
      mouse.y = (e.clientY / window.innerHeight - 0.5) * 0.4
    }
    window.addEventListener('mousemove', onMouseMove)

    // ── Animate
    let raf
    const clock = new THREE.Clock()

    const animate = () => {
      if (!mounted) return
      raf = requestAnimationFrame(animate)
      const t = clock.getElapsedTime()

      ico.rotation.x    = t * 0.25
      ico.rotation.y    = t * 0.4
      torus.rotation.x  = t * 0.35
      torus.rotation.y  = t * 0.25
      octa.rotation.y   = t * 0.6
      octa.rotation.z   = t * 0.35
      tetra.rotation.x  = t * 0.3
      tetra.rotation.z  = t * 0.25
      box.rotation.x    = t * 0.28
      box.rotation.y    = t * 0.45
      torus2.rotation.x = t * 0.2
      torus2.rotation.y = t * 0.35

      // Floating bob
      ico.position.y   = 0.4  + Math.sin(t * 0.8) * 0.3
      torus.position.y = -1.0 + Math.sin(t * 0.6 + 1) * 0.25
      octa.position.y  = 2.2  + Math.sin(t * 0.9 + 2) * 0.2

      // Mouse parallax
      scene.rotation.y = mouse.x * 0.25
      scene.rotation.x = -mouse.y * 0.18

      renderer.render(scene, camera)
    }
    animate()

    // ── Resize
    const onResize = () => {
      if (!mount) return
      const W2 = mount.clientWidth
      const H2 = mount.clientHeight
      camera.aspect = W2 / H2
      camera.updateProjectionMatrix()
      renderer.setSize(W2, H2)
    }
    window.addEventListener('resize', onResize)

    return () => {
      mounted = false
      cancelAnimationFrame(raf)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('resize', onResize)
      ;[ico, torus, octa, tetra, box, torus2].forEach(m => m.geometry.dispose())
      ;[matBlue, matPurple, matWhite].forEach(m => m.dispose())
      renderer.dispose()
      if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement)
    }
  }, [])

  return <div ref={mountRef} className="absolute inset-0 w-full h-full" />
}
