import { useEffect, useState } from 'react'
import { BarChart3, Cctv, LayoutDashboard, LogOut, MonitorPlay, Radar, Siren, Truck, Volume2, VolumeX } from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useData } from '../context/DataContext'
import ThemeToggle from './ThemeToggle'
import Toasts from './Toasts'

const NAV = [
  { to: '/', label: 'Command', code: '01', icon: LayoutDashboard, staff: true },
  { to: '/live', label: 'Live Wall', code: '02', icon: MonitorPlay, staff: true },
  { to: '/cameras', label: 'Cameras', code: '03', icon: Cctv, staff: true },
  { to: '/units', label: 'Responders', code: '04', icon: Truck, staff: true },
  { to: '/history', label: 'Analytics', code: '05', icon: BarChart3, staff: true },
  { to: '/responder', label: 'My Unit', code: 'U1', icon: Siren, staff: false },
]

function Clock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return (
    <div className="text-right leading-tight">
      <div className="mono text-[15px] font-semibold text-slate-100">{now.toLocaleTimeString([], { hour12: false })}</div>
      <div className="mono text-[9px] uppercase tracking-[.16em] text-slate-500">
        {now.toLocaleDateString([], { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })}
      </div>
    </div>
  )
}

function Meter({ label, value, tone }) {
  return (
    <div className="hidden items-baseline gap-2 border-l border-slate-800 px-4 md:flex">
      <span className="mono text-[9px] uppercase tracking-[.16em] text-slate-500">{label}</span>
      <span className={`num text-xl ${tone}`}>{value}</span>
    </div>
  )
}

export default function Layout() {
  const { user, logout, isStaff } = useAuth()
  const { connected, muted, setMuted, incidents, cameras, units } = useData()
  const { pathname } = useLocation()
  const pending = incidents.filter((i) => i.status === 'pending').length
  const active = cameras.filter((c) => c.is_active)
  const online = active.filter((c) => c.status === 'online').length
  const ready = units.filter((u) => u.status === 'available').length
  const current = NAV.find((n) => n.to === pathname) || NAV[0]

  return (
    <div className="console-bg flex h-full">
      <aside className="flex w-16 shrink-0 flex-col border-r border-slate-800 surface lg:w-56">
        <div className="flex h-14 items-center gap-3 border-b border-slate-800 px-4">
          <div className="relative flex h-8 w-8 items-center justify-center bg-[var(--color-alert)] text-black">
            <Radar size={19} strokeWidth={2.4} />
          </div>
          <div className="hidden leading-none lg:block">
            <div className="num text-xl tracking-wide">SAFEWATCH</div>
            <div className="mono mt-0.5 text-[9px] uppercase tracking-[.2em] text-slate-500">Emergency Ops</div>
          </div>
        </div>

        <nav className="flex flex-1 flex-col py-3">
          {NAV.filter((n) => (n.staff ? isStaff : user.role === 'responder' || user.unit_id)).map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end
              className={({ isActive }) =>
                `group relative flex items-center gap-3 px-5 py-2.5 text-[13px] transition ${isActive
                  ? 'bg-slate-950 text-slate-50 before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-[var(--color-signal)]'
                  : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-50'}`}
            >
              <n.icon size={18} strokeWidth={1.9} />
              <span className="hidden flex-1 font-medium lg:inline">{n.label}</span>
              <span className="mono hidden text-[9px] text-slate-600 group-hover:text-slate-500 lg:inline">{n.code}</span>
              {n.to === '/' && pending > 0 && (
                <span className="mono absolute right-2 top-1.5 bg-[var(--color-alert)] px-1.5 text-[10px] font-bold text-white lg:static">{pending}</span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-800 p-3">
          <div className="hidden px-2 pb-3 lg:block">
            <div className="truncate text-sm font-medium text-slate-100">{user.full_name || user.username}</div>
            <div className="mono text-[10px] uppercase tracking-[.16em] text-slate-500">{user.role}</div>
          </div>
          <button onClick={logout} className="flex w-full items-center gap-2 px-2 py-1.5 text-xs text-slate-400 hover:text-[var(--color-alert)]">
            <LogOut size={16} /> <span className="hidden lg:inline">Sign out</span>
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center border-b border-slate-800 surface pl-5">
          <div className="min-w-0 flex-1">
            <div className="mono text-[9px] uppercase tracking-[.2em] text-slate-500">Sector / {current.code}</div>
            <div className="num truncate text-lg uppercase tracking-wide">{current.label}</div>
          </div>
          {isStaff && (
            <>
              <Meter label="Alerts open" value={pending} tone={pending ? 'text-[var(--color-alert)]' : 'text-slate-300'} />
              <Meter label="Cams" value={`${online}/${active.length}`} tone={online === active.length && active.length ? 'text-[var(--color-ok)]' : 'text-[var(--color-signal)]'} />
              <Meter label="Units ready" value={`${ready}/${units.length}`} tone="text-slate-200" />
            </>
          )}
          <ThemeToggle className="h-full border-l border-slate-800 px-4 hover:bg-slate-950" />
          <button
            onClick={() => setMuted(!muted)}
            title={muted ? 'Alarm muted' : 'Alarm on'}
            className={`flex h-full items-center gap-2 border-l border-slate-800 px-4 text-xs ${muted ? 'text-slate-500' : 'text-slate-200'} hover:bg-slate-900`}
          >
            {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
            <span className="mono hidden text-[10px] uppercase tracking-wider xl:inline">{muted ? 'Muted' : 'Alarm'}</span>
          </button>
          <div className="flex h-full items-center gap-2 border-l border-slate-800 px-4" title={connected ? 'Real-time link active' : 'Reconnecting…'}>
            <span className={`h-2 w-2 ${connected ? 'bg-[var(--color-ok)] shadow-[0_0_10px_var(--color-ok)]' : 'blink bg-[var(--color-alert)]'}`} />
            <span className="mono text-[10px] uppercase tracking-wider text-slate-300">{connected ? 'Live link' : 'Offline'}</span>
          </div>
          <div className="flex h-full items-center border-l border-slate-800 px-5">
            <Clock />
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
      <Toasts />
    </div>
  )
}
