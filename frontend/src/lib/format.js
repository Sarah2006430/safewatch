export function timeAgo(iso) {
  if (!iso) return '—'
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return `${Math.floor(s)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

export const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString() : '—')
export const fmtClock = (iso) => (iso ? new Date(iso).toLocaleTimeString() : '—')
export const pct = (v) => `${Math.round((v || 0) * 100)}%`
export const km = (m) => (m == null ? '—' : m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`)
export const duration = (sec) => {
  if (sec == null) return '—'
  if (sec < 60) return `${Math.round(sec)}s`
  return `${Math.floor(sec / 60)}m ${Math.round(sec % 60)}s`
}
export const latlonText = (loc) => (loc ? `${loc.lat.toFixed(5)}, ${loc.lon.toFixed(5)}` : '—')
