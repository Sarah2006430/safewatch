import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api, getToken } from '../lib/api'
import { notifyBrowser, playAlarm } from '../lib/alarm'
import { INCIDENT_TYPES } from '../lib/constants'
import { useAuth } from './AuthContext'

const DataCtx = createContext(null)

function upsert(list, item, prepend = false) {
  const idx = list.findIndex((x) => x.id === item.id)
  if (idx === -1) return prepend ? [item, ...list] : [...list, item]
  const copy = list.slice()
  copy[idx] = { ...copy[idx], ...item }
  return copy
}

export function DataProvider({ children }) {
  const { user, isStaff } = useAuth()
  const [incidents, setIncidents] = useState([])
  const [cameras, setCameras] = useState([])
  const [units, setUnits] = useState([])
  const [stats, setStats] = useState(null)
  const [connected, setConnected] = useState(false)
  const [toasts, setToasts] = useState([])
  const [muted, setMuted] = useState(false)
  const listeners = useRef(new Set())
  const mutedRef = useRef(muted)
  const statsTimer = useRef(null)
  mutedRef.current = muted

  const refreshStats = useCallback(() => {
    if (!isStaff) return
    clearTimeout(statsTimer.current)
    statsTimer.current = setTimeout(() => api('/api/incidents/stats').then(setStats).catch(() => {}), 600)
  }, [isStaff])

  const reload = useCallback(async () => {
    const [inc, cams, us] = await Promise.all([
      api('/api/incidents?since_hours=168&limit=400'),
      api('/api/cameras'),
      api('/api/units'),
    ])
    setIncidents(inc)
    setCameras(cams)
    setUnits(us)
    refreshStats()
  }, [refreshStats])

  const subscribe = useCallback((fn) => {
    listeners.current.add(fn)
    return () => listeners.current.delete(fn)
  }, [])

  const dismissToast = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), [])

  const handle = useCallback((msg) => {
    const { event, data } = msg
    switch (event) {
      case 'incident_created': {
        setIncidents((l) => upsert(l, data, true))
        const meta = INCIDENT_TYPES[data.type]
        const toastId = `${data.id}-${Date.now()}`
        setToasts((t) => [...t.slice(-3), { id: toastId, incident: data }])
        setTimeout(() => dismissToast(toastId), 12000)
        if (!mutedRef.current) playAlarm(data.severity === 'critical')
        notifyBrowser(`ALERT · ${meta?.label || data.type} detected`, `${data.camera_name || 'Camera'} — confidence ${Math.round(data.confidence * 100)}%`)
        refreshStats()
        break
      }
      case 'incident_updated':
        setIncidents((l) => upsert(l, data, true))
        refreshStats()
        break
      case 'camera_updated':
        setCameras((l) => upsert(l, data))
        break
      case 'camera_deleted':
        setCameras((l) => l.filter((c) => c.id !== data.id))
        break
      case 'unit_updated':
        setUnits((l) => upsert(l, data))
        break
      case 'unit_deleted':
        setUnits((l) => l.filter((u) => u.id !== data.id))
        break
      default:
        break
    }
    listeners.current.forEach((fn) => fn(msg))
  }, [dismissToast, refreshStats])

  // Initial load + periodic stats refresh
  useEffect(() => {
    if (!user) return
    reload().catch(console.error)
    const t = setInterval(refreshStats, 30000)
    return () => clearInterval(t)
  }, [user, reload, refreshStats])

  // WebSocket with auto-reconnect
  useEffect(() => {
    if (!user) return
    let ws, pingTimer, retryTimer
    let closed = false
    let attempt = 0

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(getToken() || '')}`)
      ws.onopen = () => {
        attempt = 0
        setConnected(true)
        pingTimer = setInterval(() => ws.readyState === 1 && ws.send('ping'), 25000)
        reload().catch(() => {}) // catch up on anything missed while disconnected
      }
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.event !== 'pong') handle(msg)
        } catch { /* ignore */ }
      }
      ws.onclose = () => {
        setConnected(false)
        clearInterval(pingTimer)
        if (!closed) retryTimer = setTimeout(connect, Math.min(1000 * 2 ** attempt++, 15000))
      }
    }
    connect()
    return () => {
      closed = true
      clearInterval(pingTimer)
      clearTimeout(retryTimer)
      ws?.close()
    }
  }, [user, handle, reload])

  return (
    <DataCtx.Provider value={{
      incidents, cameras, units, stats, connected, toasts, muted,
      setMuted, dismissToast, subscribe, reload, refreshStats, setIncidents,
    }}>
      {children}
    </DataCtx.Provider>
  )
}

export const useData = () => useContext(DataCtx)
