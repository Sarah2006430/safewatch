import L from 'leaflet'
import { renderToStaticMarkup } from 'react-dom/server'
import { Cctv } from 'lucide-react'
import { AGENCIES, INCIDENT_TYPES } from './constants'

const cache = new Map()

function icon(key, html, size) {
  if (!cache.has(key)) {
    cache.set(key, L.divIcon({ html, className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2], popupAnchor: [0, -size / 2] }))
  }
  return cache.get(key)
}

const svg = (Icon, size, stroke = 2.4) => renderToStaticMarkup(<Icon size={size} strokeWidth={stroke} />)

export function incidentIcon(type, status, selected) {
  const meta = INCIDENT_TYPES[type] || INCIDENT_TYPES.fall
  const size = selected ? 34 : 28
  const closed = !['pending', 'verified', 'dispatched'].includes(status)
  const pulse = status === 'pending' ? 'pulse' : ''
  return icon(`inc-${type}-${status}-${selected}`,
    `<div class="mk mk-inc ${pulse}" style="width:${size}px;height:${size}px;background:${closed ? '#434a4d' : meta.color};color:${meta.color};--pc:${meta.color}">${svg(meta.Icon, selected ? 18 : 15)}</div>`,
    size)
}

export function unitIcon(agency, status) {
  const meta = AGENCIES[agency] || AGENCIES.police
  const busy = status !== 'available' && status !== 'offline'
  const style = status === 'offline' ? 'opacity:.4;' : ''
  const ring = busy ? 'box-shadow:0 0 0 2px #ffb020,0 2px 8px rgba(0,0,0,.6);' : ''
  return icon(`unit-${agency}-${status}`,
    `<div class="mk mk-unit" style="width:24px;height:24px;background:${meta.color};${style}${ring}">${svg(meta.Icon, 14)}</div>`,
    24)
}

export function cameraIcon(status, active) {
  const color = !active ? '#434a4d' : status === 'online' ? '#2fd27a' : status === 'unknown' ? '#5f676a' : '#ff3b30'
  return icon(`cam-${status}-${active}`,
    `<div class="mk mk-cam" style="width:22px;height:22px;border-color:${color};color:${color}">${svg(Cctv, 12, 2.2)}</div>`,
    22)
}

export const OSM_TILES = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
export const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
