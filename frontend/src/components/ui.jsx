import { X } from 'lucide-react'
import { SEVERITY_STYLES, STATUS_STYLES } from '../lib/constants'

export function StatusBadge({ status }) {
  return (
    <span className={`mono inline-flex items-center gap-1 border px-1.5 py-px text-[10px] font-semibold uppercase tracking-wider ${STATUS_STYLES[status] || STATUS_STYLES.false_alarm}`}>
      {status === 'pending' && <span className="blink h-1.5 w-1.5 bg-current" />}
      {status?.replace('_', ' ')}
    </span>
  )
}

export function SeverityBadge({ severity }) {
  return (
    <span className={`mono px-1.5 py-px text-[10px] font-bold uppercase tracking-wider ${SEVERITY_STYLES[severity] || SEVERITY_STYLES.low}`}>
      {severity}
    </span>
  )
}

const VARIANTS = {
  primary: 'bg-[var(--color-signal)] text-[var(--on-signal)] hover:brightness-110',
  danger: 'bg-[var(--color-alert)] text-white hover:brightness-110',
  success: 'bg-[var(--color-ok)] text-white hover:brightness-110',
  warning: 'bg-[var(--color-signal)] text-[var(--on-signal)] hover:brightness-110',
  ghost: 'bg-transparent text-slate-200 border border-slate-600 hover:border-slate-400 hover:bg-slate-800',
}

export function Button({ variant = 'primary', className = '', children, ...props }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 px-3 py-2 text-[13px] font-semibold uppercase tracking-wide transition disabled:cursor-not-allowed disabled:opacity-40 ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

export function Card({ className = '', children }) {
  return <div className={`border border-slate-800 bg-slate-900 ${className}`}>{children}</div>
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mono mb-1 block text-[10px] uppercase tracking-[.14em] text-slate-400">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-slate-500">{hint}</span>}
    </label>
  )
}

export const inputCls =
  'w-full border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 outline-none transition focus:border-[var(--color-signal)]'

export function Modal({ title, onClose, children, wide }) {
  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-slate-50/40 p-4 backdrop-blur-[3px]" onMouseDown={onClose}>
      <div
        className={`rise max-h-[92vh] w-full overflow-y-auto border border-slate-700 bg-slate-900 shadow-[0_30px_80px_rgba(0,0,0,.3)] scroll-thin ${wide ? 'max-w-5xl' : 'max-w-xl'}`}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-800 bg-slate-900 px-5 py-3">
          <h2 className="num text-lg uppercase tracking-wide">{title}</h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-50"><X size={18} /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

export function Empty({ children }) {
  return <div className="mono py-10 text-center text-xs uppercase tracking-wider text-slate-500">{children}</div>
}

/** Page header used by the secondary screens. */
export function PageHeader({ kicker, title, children }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3 border-b border-slate-800 pb-4">
      <div>
        <div className="label">{kicker}</div>
        <h1 className="num mt-1 text-3xl uppercase">{title}</h1>
      </div>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  )
}

/** Coloured square icon tile for an incident type / agency. */
export function Tile({ meta, size = 36, className = '' }) {
  const Icon = meta?.Icon
  return (
    <div className={`flex shrink-0 items-center justify-center text-black ${className}`} style={{ width: size, height: size, background: meta?.color || '#5f676a' }}>
      {Icon && <Icon size={Math.round(size * 0.55)} strokeWidth={2.3} />}
    </div>
  )
}
