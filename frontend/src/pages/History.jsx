import { useEffect, useMemo, useState } from 'react'
import { Download } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Benchmark from '../components/Benchmark'
import SessionHistory from '../components/SessionHistory'
import { api } from '../lib/api'
import { Button, Card, Empty, inputCls, PageHeader, SeverityBadge, StatusBadge } from '../components/ui'
import { useData } from '../context/DataContext'
import { INCIDENT_TYPES } from '../lib/constants'
import { duration, fmtTime, pct } from '../lib/format'

function Bars({ data }) {
  const max = Math.max(1, ...data.map((d) => d.value))
  return (
    <div className="space-y-2">
      {data.map((d) => (
        <div key={d.key} className="flex items-center gap-2 text-xs">
          <span className="mono flex w-28 items-center gap-1.5 truncate text-[11px] uppercase text-slate-400"><span style={{ color: d.color }}>{d.icon}</span>{d.label}</span>
          <div className="h-4 flex-1 bg-slate-800/60">
            <div className="h-full" style={{ width: `${(d.value / max) * 100}%`, background: d.color }} />
          </div>
          <span className="num w-8 text-right text-lg text-slate-100">{d.value}</span>
        </div>
      ))}
    </div>
  )
}

function Hourly({ hourly }) {
  const buckets = useMemo(() => {
    const now = new Date()
    now.setMinutes(0, 0, 0)
    const map = Object.fromEntries((hourly || []).map((h) => [new Date(h.hour).getTime(), h.count]))
    return Array.from({ length: 24 }, (_, i) => {
      const t = now.getTime() - (23 - i) * 3600e3
      return { t, count: map[t] || 0 }
    })
  }, [hourly])
  const max = Math.max(1, ...buckets.map((b) => b.count))
  return (
    <div>
      <div className="flex h-28 items-end gap-1">
        {buckets.map((b) => (
          <div key={b.t} className="group relative flex-1">
            <div className="bg-[var(--color-signal)]/70 group-hover:bg-[var(--color-signal)]" style={{ height: `${Math.max(2, (b.count / max) * 104)}px` }} />
            <div className="pointer-events-none absolute -top-6 left-1/2 hidden -translate-x-1/2 whitespace-nowrap mono bg-slate-800 px-1.5 text-[10px] group-hover:block">
              {new Date(b.t).getHours()}:00 · {b.count}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-slate-500"><span>24h ago</span><span>now</span></div>
    </div>
  )
}

function exportCsv(rows) {
  const cols = ['id', 'type', 'severity', 'status', 'camera_name', 'detected_at', 'confidence', 'detection_count', 'lat', 'lon', 'notes']
  const esc = (v) => `"${String(v ?? '').replaceAll('"', '""')}"`
  const lines = rows.map((i) => [i.id, i.type, i.severity, i.status, i.camera_name, i.detected_at, i.confidence, i.detection_count,
    i.location?.lat, i.location?.lon, i.notes].map(esc).join(','))
  const blob = new Blob([[cols.join(','), ...lines].join('\n')], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `safewatch-incidents-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function History() {
  const { incidents: live, stats } = useData()
  const navigate = useNavigate()
  const [type, setType] = useState('')
  const [status, setStatus] = useState('')
  const [q, setQ] = useState('')
  const [range, setRange] = useState('168')
  const [archive, setArchive] = useState(null)

  // Full history comes from PostgreSQL (kept across restarts); refetch when live data changes.
  useEffect(() => {
    const qs = range === 'all' ? 'limit=1000' : `since_hours=${range}&limit=1000`
    api(`/api/incidents?${qs}`).then(setArchive).catch(() => setArchive(null))
  }, [range, live.length])
  const incidents = archive || live

  const rows = incidents.filter((i) =>
    (!type || i.type === type) && (!status || i.status === status) &&
    (!q || `${i.id} ${i.camera_name} ${i.notes}`.toLowerCase().includes(q.toLowerCase())))

  const byType = Object.entries(INCIDENT_TYPES).map(([k, m]) => ({ key: k, label: m.short, icon: m.icon, color: m.color, value: stats?.last_24h?.by_type?.[k] || 0 }))

  return (
    <div className="scroll-thin h-full overflow-y-auto p-4">
      <PageHeader kicker="Detection and response performance" title="Analytics & history" />
      <Benchmark />
      <div className="mb-4 grid gap-4 lg:grid-cols-3">
        <Card className="p-4"><div className="label mb-4">Alerts by type · 24 h</div><Bars data={byType} /></Card>
        <Card className="p-4"><div className="label mb-4">Alerts per hour · 24 h</div><Hourly hourly={stats?.hourly} /></Card>
        <Card className="space-y-3 p-4 text-sm">
          <div className="label">Response performance · 7 days</div>
          <div className="flex justify-between"><span className="text-slate-400">Avg. time to verify</span><b className="num text-xl font-semibold">{duration(stats?.avg_seconds_to_verify)}</b></div>
          <div className="flex justify-between"><span className="text-slate-400">Avg. time to dispatch</span><b className="num text-xl font-semibold">{duration(stats?.avg_seconds_to_dispatch)}</b></div>
          <div className="flex justify-between"><span className="text-slate-400">False alarm rate (24h)</span><b className="num text-xl font-semibold">{pct(stats?.false_alarm_rate)}</b></div>
          <div className="flex justify-between"><span className="text-slate-400">Open incidents</span><b className="num text-xl font-semibold">{stats?.open_total ?? 0}</b></div>
        </Card>
      </div>

      <Card className="p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <select className={`${inputCls} max-w-[10rem]`} value={range} onChange={(e) => setRange(e.target.value)}>
            <option value="24">Last 24 hours</option>
            <option value="168">Last 7 days</option>
            <option value="720">Last 30 days</option>
            <option value="all">All time</option>
          </select>
          <input className={`${inputCls} max-w-xs`} placeholder="Search id, camera, notes…" value={q} onChange={(e) => setQ(e.target.value)} />
          <select className={`${inputCls} max-w-[12rem]`} value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">All types</option>
            {Object.entries(INCIDENT_TYPES).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
          </select>
          <select className={`${inputCls} max-w-[12rem]`} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {['pending', 'verified', 'dispatched', 'resolved', 'false_alarm'].map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
          </select>
          <span className="mono ml-auto text-[10px] uppercase text-slate-500">{rows.length} incidents</span>
          <Button variant="ghost" disabled={!rows.length} onClick={() => exportCsv(rows)}><Download size={14} /> CSV</Button>
        </div>
        {!rows.length ? <Empty>No incidents match.</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="mono text-[10px] uppercase tracking-wider text-slate-500">
                <tr><th className="p-2">#</th><th className="p-2">Type</th><th className="p-2">Severity</th><th className="p-2">Camera</th><th className="p-2">Detected</th><th className="p-2">Confidence</th><th className="p-2">Status</th></tr>
              </thead>
              <tbody>
                {rows.map((i) => (
                  <tr key={i.id} className="cursor-pointer border-t border-slate-800 hover:bg-slate-800/50" onClick={() => navigate(`/?incident=${i.id}`)}>
                    <td className="mono p-2 text-[11px] text-slate-500">{String(i.id).padStart(4, '0')}</td>
                    <td className="p-2"><span className="inline-flex items-center gap-1.5"><span style={{ color: INCIDENT_TYPES[i.type]?.color }}>{INCIDENT_TYPES[i.type]?.icon}</span>{INCIDENT_TYPES[i.type]?.label}</span></td>
                    <td className="p-2"><SeverityBadge severity={i.severity} /></td>
                    <td className="p-2">{i.camera_name || <span className="text-slate-500">Deleted camera</span>}</td>
                    <td className="p-2 text-slate-400">{fmtTime(i.detected_at)}</td>
                    <td className="p-2">{pct(i.confidence)}</td>
                    <td className="p-2"><StatusBadge status={i.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <SessionHistory />
    </div>
  )
}
