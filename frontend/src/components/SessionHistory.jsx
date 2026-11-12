import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { fmtTime } from '../lib/format'
import { Card, Empty } from './ui'

const KIND = {
  signup: 'text-[var(--color-signal)]',
  login: 'text-[var(--color-ok)]',
  logout: 'text-slate-400',
  failed: 'text-[var(--color-alert)]',
}

function browser(ua = '') {
  if (/curl/i.test(ua)) return 'curl'
  if (/Edg\//.test(ua)) return 'Edge'
  if (/Chrome\//.test(ua)) return 'Chrome'
  if (/Firefox\//.test(ua)) return 'Firefox'
  if (/Safari\//.test(ua)) return 'Safari'
  return ua.split(' ')[0] || '—'
}

/** Sign-up / sign-in / sign-out history, stored in PostgreSQL across sessions. */
export default function SessionHistory() {
  const [rows, setRows] = useState(null)
  useEffect(() => { api('/api/auth/sessions?limit=50').then(setRows).catch(() => setRows([])) }, [])
  return (
    <Card className="mt-4 p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <div className="label">Sign-in history</div>
        <div className="mono text-[10px] text-slate-500">admins see all users · others see their own</div>
      </div>
      {!rows ? <Empty>Loading…</Empty> : !rows.length ? <Empty>No sessions recorded yet</Empty> : (
        <div className="scroll-thin max-h-72 overflow-y-auto">
          <table className="w-full text-left text-sm">
            <thead className="mono text-[10px] uppercase tracking-wider text-slate-500">
              <tr><th className="p-2">When</th><th className="p-2">User</th><th className="p-2">Event</th><th className="p-2">From</th><th className="p-2">Client</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-slate-800">
                  <td className="mono p-2 text-[11px] text-slate-400">{fmtTime(r.created_at)}</td>
                  <td className="p-2">{r.username}</td>
                  <td className={`mono p-2 text-[11px] font-semibold uppercase ${KIND[r.kind] || ''}`}>{r.kind}</td>
                  <td className="mono p-2 text-[11px] text-slate-400">{r.ip}</td>
                  <td className="p-2 text-xs text-slate-400">{browser(r.user_agent)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
