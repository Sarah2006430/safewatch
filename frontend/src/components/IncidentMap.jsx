import { useEffect, useMemo, useRef } from 'react'
import { LayerGroup, LayersControl, MapContainer, Marker, Polygon, Polyline, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { AGENCIES, INCIDENT_TYPES, OPEN_STATUSES } from '../lib/constants'
import { cameraIcon, incidentIcon, OSM_ATTRIBUTION, OSM_TILES, unitIcon } from '../lib/mapIcons'
import { timeAgo } from '../lib/format'

export const DEFAULT_CENTER = [12.9716, 77.5946]

export function mapCenter(cameras = [], units = []) {
  const pts = [...cameras, ...units].map((x) => x.location).filter(Boolean)
  if (!pts.length) return DEFAULT_CENTER
  return [pts.reduce((a, p) => a + p.lat, 0) / pts.length, pts.reduce((a, p) => a + p.lon, 0) / pts.length]
}

function FlyTo({ target }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.flyTo([target.lat, target.lon], Math.max(map.getZoom(), 15), { duration: 0.8 })
  }, [target?.lat, target?.lon]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

function FitOnce({ points }) {
  const map = useMap()
  const done = useRef(false)
  useEffect(() => {
    if (done.current || points.length < 2) return
    done.current = true
    map.fitBounds(points, { padding: [40, 40], maxZoom: 15 })
  }, [points, map])
  return null
}

export default function IncidentMap({ incidents, cameras, units, selected, onSelect, showClosed = false }) {
  const visible = useMemo(
    () => incidents.filter((i) => i.location && (showClosed || OPEN_STATUSES.includes(i.status) || i.id === selected?.id)),
    [incidents, showClosed, selected?.id],
  )
  const fitPoints = useMemo(
    () => [...cameras, ...units].map((x) => x.location).filter(Boolean).map((l) => [l.lat, l.lon]),
    [cameras, units],
  )
  const unitById = useMemo(() => Object.fromEntries(units.map((u) => [u.id, u])), [units])

  const lines = (selected?.dispatches || [])
    .filter((d) => !['completed', 'cancelled'].includes(d.status))
    .map((d) => ({ d, unit: unitById[d.unit_id] || d.unit }))
    .filter(({ unit }) => unit?.location && selected?.location)

  return (
    <MapContainer center={mapCenter(cameras, units)} zoom={13} className="h-full w-full" zoomControl>
      <TileLayer url={OSM_TILES} attribution={OSM_ATTRIBUTION} className="dark-tiles" />
      <FitOnce points={fitPoints} />
      <FlyTo target={selected?.location} />

      <LayersControl position="topright">
        <LayersControl.Overlay checked name="Incidents">
          <LayerGroup>
            {visible.map((i) => (
              <Marker
                key={`i${i.id}`}
                position={[i.location.lat, i.location.lon]}
                icon={incidentIcon(i.type, i.status, selected?.id === i.id)}
                zIndexOffset={1000}
                eventHandlers={{ click: () => onSelect?.(i.id) }}
              >
                <Tooltip direction="top" offset={[0, -14]}>
                  <b>{INCIDENT_TYPES[i.type]?.label}</b> · <span className="uppercase">{i.status.replace('_', ' ')}</span><br />
                  {i.camera_name} · {timeAgo(i.detected_at)}
                </Tooltip>
              </Marker>
            ))}
          </LayerGroup>
        </LayersControl.Overlay>

        <LayersControl.Overlay checked name="Responders">
          <LayerGroup>
            {units.filter((u) => u.location).map((u) => (
              <Marker key={`u${u.id}`} position={[u.location.lat, u.location.lon]} icon={unitIcon(u.agency, u.status)}>
                <Popup>
                  <div className="flex items-center gap-1.5 text-sm font-semibold"><span style={{ color: AGENCIES[u.agency]?.color }}>{AGENCIES[u.agency]?.icon}</span>{u.name}</div>
                  <div className="mono text-[10px] uppercase tracking-wider text-slate-400">{AGENCIES[u.agency]?.label} · {u.status.replace('_', ' ')}</div>
                  {u.contact && <div className="mono text-[11px] text-slate-300">TEL {u.contact}</div>}
                </Popup>
              </Marker>
            ))}
          </LayerGroup>
        </LayersControl.Overlay>

        <LayersControl.Overlay checked name="Cameras">
          <LayerGroup>
            {cameras.filter((c) => c.location).map((c) => (
              <Marker key={`c${c.id}`} position={[c.location.lat, c.location.lon]} icon={cameraIcon(c.status, c.is_active)}>
                <Popup>
                  <div className="text-sm font-semibold">CAM{String(c.id).padStart(2, '0')} · {c.name}</div>
                  <div className="text-xs text-slate-400">{c.address}</div>
                  <div className="mono text-[10px] uppercase tracking-wider text-slate-400">{c.is_active ? c.status : 'disabled'}</div>
                </Popup>
              </Marker>
            ))}
          </LayerGroup>
        </LayersControl.Overlay>

        <LayersControl.Overlay checked name="Zones">
          <LayerGroup>
            {cameras.flatMap((c) => c.zones.filter((z) => z.area?.length >= 3).map((z) => (
              <Polygon
                key={`z${z.id}`}
                positions={z.area.map(([la, lo]) => [la, lo])}
                pathOptions={z.kind === 'restricted'
                  ? { color: '#e8c547', weight: 1.5, fillOpacity: 0.12, dashArray: '5 4' }
                  : { color: '#25b8e8', weight: 1.5, fillOpacity: 0.18 }}
              >
                <Tooltip sticky>{z.kind === 'restricted' ? 'RESTRICTED' : 'WATER'} · {z.name}</Tooltip>
              </Polygon>
            )))}
          </LayerGroup>
        </LayersControl.Overlay>
      </LayersControl>

      {lines.map(({ d, unit }) => (
        <Polyline
          key={`l${d.id}`}
          positions={[[unit.location.lat, unit.location.lon], [selected.location.lat, selected.location.lon]]}
          pathOptions={{ color: AGENCIES[unit.agency]?.color || '#fff', weight: 2.5, dashArray: '2 7', lineCap: 'square' }}
        />
      ))}
    </MapContainer>
  )
}
