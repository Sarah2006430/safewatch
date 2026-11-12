import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import { applyTheme, getTheme } from '../lib/theme'

export default function ThemeToggle({ className = '' }) {
  const [theme, setTheme] = useState(getTheme)
  useEffect(() => {
    const on = (e) => setTheme(e.detail)
    window.addEventListener('theme:change', on)
    return () => window.removeEventListener('theme:change', on)
  }, [])
  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      onClick={() => applyTheme(next)}
      title={`Switch to ${next} theme`}
      className={`flex items-center gap-2 text-xs text-slate-300 hover:text-slate-50 ${className}`}
    >
      {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
      <span className="mono hidden text-[10px] uppercase tracking-wider xl:inline">{next}</span>
    </button>
  )
}
