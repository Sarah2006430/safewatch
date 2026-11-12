import { useData } from '../context/DataContext'
import { AGENCIES } from '../lib/constants'
import { duration } from '../lib/format'

function Cell({ label, value, tone = 'text-slate-100', sub, alert }) {
  return (
    <div className={`relative min-w-[8.5rem] flex-1 border-r border-slate-800 px-4 py-2.5 ${alert ? 'bg-[var(--color-alert)]/[.07]' : ''}`}>
      {alert && <div className="hazard absolute inset-x-0 top-0 h-[3px]" />}
      <div className="mono text-[9px] uppercase tracking-[.16em] text-slate-500">{label}</div>
      <div className={`num mt-1 text-[30px] ${tone}`}>{value}</div>
      {sub && <div className="mono mt-0.5 text-[10px] text-slate-500">{sub}</div>}
    </div>
  )
}

function AgencyCell({ agency, units }) {
  const a = AGENCIES[agency]
  const all = units.filter((u) => u.agency === agency)
  const free = all.filter((u) => u.status === 'available').length
  return (
    <div className="min-w-[7.5rem] flex-1 border-r border-slate-800 px-4 py-2.5">
      <div className="mono flex items-center gap-1.5 text-[9px] uppercase tracking-[.16em] text-slate-500">
        <span style={{ color: a.color }}>{a.icon}</span>{a.label}
      </div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="num text-[30px] text-slate-100">{free}</span>
        <span className="mono text-[11px] text-slate-500">/ {all.length} ready</span>
      </div>
      <div className="mt-1.5 flex gap-[3px]">
        {all.map((u) => (
          <span key={u.id} className="h-1 flex-1" style={{ background: u.status === 'available' ? a.color : u.status === 'offline' ? '#2c3235' : '#ffb020' }} />
        ))}
      </div>
    </div>
  )
}

export default function StatsBar() {
  const { stats, units } = useData()
  const pending = stats?.open?.pending ?? 0
  return (
    <div className="scroll-thin flex overflow-x-auto border-b border-slate-800 panel">
      <Cell label="Awaiting verification" value={pending} tone={pending ? 'text-[var(--color-alert)]' : 'text-slate-300'} alert={pending > 0} />
      <Cell label="Verified" value={stats?.open?.verified ?? 0} tone="text-[var(--color-signal)]" />
      <Cell label="Units dispatched" value={stats?.open?.dispatched ?? 0} tone="text-[var(--color-info)]" />
      <Cell label="Alerts · 24 h" value={stats?.last_24h?.total ?? 0} sub={`${Math.round((stats?.false_alarm_rate || 0) * 100)}% false alarm rate`} />
      <Cell label="Mean time to verify" value={duration(stats?.avg_seconds_to_verify)} sub="rolling 7 days" />
      {Object.keys(AGENCIES).map((k) => <AgencyCell key={k} agency={k} units={units} />)}
    </div>
  )
}
