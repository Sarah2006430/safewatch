import { useEffect } from 'react'
import L from 'leaflet'
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import { OSM_ATTRIBUTION, OSM_TILES } from '../lib/mapIcons'
import { DEFAULT_CENTER } from './IncidentMap'

const pin = L.divIcon({
  html: '<div class="mk mk-inc pulse" style="width:20px;height:20px;background:#ffb020;color:#ffb020;--pc:#ffb020"></div>',
  className: '', iconSize: [22, 22], iconAnchor: [11, 11],
})

function Clicker({ onChange }) {
  useMapEvents({ click: (e) => onChange({ lat: +e.latlng.lat.toFixed(6), lon: +e.latlng.lng.toFixed(6) }) })
  return null
}

function Recenter({ value }) {
  const map = useMap()
  useEffect(() => { if (value) map.panTo([value.lat, value.lon]) }, [value?.lat, value?.lon]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

/** Click on the map to pick a location (used for cameras and response units). */
export default function MapPicker({ value, onChange, center = DEFAULT_CENTER, height = 240 }) {
  return (
    <div style={{ height }} className="overflow-hidden rounded-lg border border-slate-700">
      <MapContainer center={value ? [value.lat, value.lon] : center} zoom={14} className="h-full w-full">
        <TileLayer url={OSM_TILES} attribution={OSM_ATTRIBUTION} className="dark-tiles" />
        <Clicker onChange={onChange} />
        <Recenter value={value} />
        {value && (
          <Marker
            position={[value.lat, value.lon]}
            icon={pin}
            draggable
            eventHandlers={{ dragend: (e) => { const p = e.target.getLatLng(); onChange({ lat: +p.lat.toFixed(6), lon: +p.lng.toFixed(6) }) } }}
          />
        )}
      </MapContainer>
    </div>
  )
}
