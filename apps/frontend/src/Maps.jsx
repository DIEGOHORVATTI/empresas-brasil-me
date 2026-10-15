import { useEffect, useMemo, useState } from 'react'
import {
  Input, Select, SelectItem, Button, Table, TableHeader, TableColumn,
  TableBody, TableRow, TableCell, Link, Spinner, Chip, Switch,
} from '@heroui/react'
import {
  MapContainer, TileLayer, Circle, CircleMarker, Marker, Popup, useMap, useMapEvents,
} from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const UFS = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA',
  'PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO']
// zoom do Maps ≈ raio da área. Menor zoom = área maior. km usado no círculo/filtro.
const RAIOS = [
  { k: '15', v: 'Bairro (~1 km)', km: 1 },
  { k: '14', v: 'Região (~3 km)', km: 3 },
  { k: '13', v: 'Cidade (~6 km)', km: 6 },
  { k: '12', v: 'Cidade grande (~12 km)', km: 12 },
]
const KM = Object.fromEntries(RAIOS.map((r) => [r.k, r.km]))
const ZOOM_LEAFLET = { '15': 15, '14': 14, '13': 13, '12': 12 }
const CENTRO_BR = [-15.78, -47.93] // Brasília, fallback inicial
const pin = L.divIcon({
  html: '<div style="font-size:26px;line-height:1;transform:translate(-50%,-90%)">📍</div>',
  className: '', iconSize: [0, 0],
})

// Recentraliza o mapa quando o centro muda pelos campos (fields -> map).
function Recentralizar({ centro, zoom }) {
  const map = useMap()
  useEffect(() => { if (centro) map.setView(centro, zoom) }, [centro?.[0], centro?.[1], zoom])
  return null
}

// Clique no mapa vira novo centro (map -> fields).
function AoClicar({ onPick }) {
  useMapEvents({ click: (e) => onPick([e.latlng.lat, e.latlng.lng]) })
  return null
}

export default function Maps() {
  const [query, setQuery] = useState('')
  const [cidade, setCidade] = useState('')
  const [uf, setUf] = useState('')
  const [zoom, setZoom] = useState('14')
  const [max, setMax] = useState('20')
  const [centro, setCentro] = useState(null) // [lat,lng] escolhido/geocodado
  const [filtrarMapa, setFiltrarMapa] = useState(true)
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState('')
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)

  const raioKm = KM[zoom] || 3
  const zoomLeaflet = ZOOM_LEAFLET[zoom] || 14

  const carregar = () =>
    fetch('/api/maps/empresas?limit=500')
      .then((r) => r.json())
      .then((d) => { setRows(d.results); setTotal(d.total) })
  useEffect(() => { carregar() }, [])

  // Campos cidade/uf -> centro do mapa (geocode).
  const geocodar = () => {
    if (!cidade.trim()) return
    fetch(`/api/maps/geocode?cidade=${encodeURIComponent(cidade)}&uf=${uf}`)
      .then((r) => r.json())
      .then((d) => { if (d.lat) setCentro([d.lat, d.lng]) })
  }

  // Centro escolhido no mapa -> preenche cidade/uf (reverse geocode).
  const escolherNoMapa = (latlng) => {
    setCentro(latlng)
    fetch(`/api/maps/reverse?lat=${latlng[0]}&lng=${latlng[1]}`)
      .then((r) => r.json())
      .then((d) => { if (d.cidade) setCidade(d.cidade); if (d.uf) setUf(d.uf) })
  }

  const buscar = () => {
    if (!query.trim() || (!cidade.trim() && !centro)) {
      setErro('Preencha o que buscar e a cidade (ou clique um ponto no mapa).')
      return
    }
    setErro(''); setLoading(true)
    fetch('/api/maps/buscar', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        query, cidade, uf, zoom: Number(zoom), max: Number(max),
        lat: centro?.[0], lng: centro?.[1],
      }),
    })
      .then((r) => r.json())
      .then((d) => {
        setLoading(false)
        if (d.erro) { setErro(d.erro); return }
        carregar()
      })
      .catch((e) => { setLoading(false); setErro(String(e)) })
  }

  // Pontos no mapa + filtro do círculo (map <-> tabela).
  const comCoord = useMemo(
    () => rows.filter((r) => r.latitude != null && r.longitude != null), [rows])
  const visiveis = useMemo(() => {
    if (!filtrarMapa || !centro) return rows
    const c = L.latLng(centro[0], centro[1])
    return rows.filter((r) => r.latitude != null &&
      c.distanceTo(L.latLng(r.latitude, r.longitude)) <= raioKm * 1000)
  }, [rows, filtrarMapa, centro, raioKm])

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
      {/* campos no topo */}
      <div className="px-6 pt-4 pb-3 shrink-0 flex flex-wrap items-end gap-3">
        <Input label="O que buscar" size="sm" className="w-52" placeholder="ex: restaurante, imobiliária"
          value={query} onValueChange={setQuery} />
        <Input label="Cidade" size="sm" className="w-40" placeholder="ex: Campinas"
          value={cidade} onValueChange={setCidade} onBlur={geocodar} />
        <Select label="UF" size="sm" className="w-20" selectedKeys={uf ? [uf] : []}
          onChange={(e) => { setUf(e.target.value); if (cidade) geocodar() }}>
          {UFS.map((u) => <SelectItem key={u}>{u}</SelectItem>)}
        </Select>
        <Select label="Raio" size="sm" className="w-44" selectedKeys={[zoom]}
          onChange={(e) => e.target.value && setZoom(e.target.value)}>
          {RAIOS.map((r) => <SelectItem key={r.k}>{r.v}</SelectItem>)}
        </Select>
        <Input label="Máx." size="sm" className="w-20" inputMode="numeric"
          value={max} onValueChange={(v) => setMax(v.replace(/\D/g, ''))} />
        <Button color="primary" onPress={buscar} isLoading={loading}>
          {loading ? 'Coletando…' : 'Buscar no Maps'}
        </Button>
        <Switch size="sm" isSelected={filtrarMapa} onValueChange={setFiltrarMapa}>
          Filtrar pelo raio
        </Switch>
        {erro && <span className="text-tiny text-danger self-center">{erro}</span>}
      </div>

      {loading && (
        <div className="px-6 pb-2 shrink-0">
          <Spinner size="sm" label="Abrindo o Maps e raspando (pode levar 1-2 min)…" />
        </div>
      )}

      {/* mapa (esquerda) + tabela (direita) */}
      <div className="px-6 pb-4 flex-1 min-h-0 flex gap-4">
        <div className="w-[42%] min-w-[320px] rounded-large overflow-hidden border border-divider">
          <MapContainer center={centro || CENTRO_BR} zoom={centro ? zoomLeaflet : 4}
            className="h-full w-full" scrollWheelZoom>
            <TileLayer
              attribution="&copy; OpenStreetMap"
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <Recentralizar centro={centro} zoom={zoomLeaflet} />
            <AoClicar onPick={escolherNoMapa} />
            {centro && (
              <>
                <Circle center={centro} radius={raioKm * 1000}
                  pathOptions={{ color: '#3b82f6', fillOpacity: 0.08 }} />
                <Marker position={centro} icon={pin} draggable
                  eventHandlers={{ dragend: (e) => escolherNoMapa(
                    [e.target.getLatLng().lat, e.target.getLatLng().lng]) }} />
              </>
            )}
            {comCoord.map((r) => (
              <CircleMarker key={r.place_id} center={[r.latitude, r.longitude]} radius={5}
                pathOptions={{ color: '#16a34a', fillColor: '#16a34a', fillOpacity: 0.9 }}>
                <Popup>
                  <b>{r.nome}</b><br />{r.categoria || ''}<br />{r.telefone || ''}
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>

        <div className="flex-1 min-w-0 flex flex-col">
          <Table aria-label="Empresas do Maps" isHeaderSticky
            classNames={{ base: 'flex-1 min-h-0 flex flex-col', wrapper: 'flex-1 min-h-0' }}>
            <TableHeader>
              <TableColumn>NOME</TableColumn>
              <TableColumn>CATEGORIA</TableColumn>
              <TableColumn>ENDEREÇO</TableColumn>
              <TableColumn>TELEFONE</TableColumn>
              <TableColumn>SITE</TableColumn>
              <TableColumn>NOTA</TableColumn>
            </TableHeader>
            <TableBody items={visiveis}
              emptyContent="Nenhuma empresa aqui. Busque acima ou amplie o raio.">
              {(r) => (
                <TableRow key={r.place_id}>
                  <TableCell className="max-w-[200px] truncate">{r.nome || '—'}</TableCell>
                  <TableCell>{r.categoria || '—'}</TableCell>
                  <TableCell className="max-w-[220px] truncate">{r.endereco || '—'}</TableCell>
                  <TableCell className="whitespace-nowrap">{r.telefone || '—'}</TableCell>
                  <TableCell>
                    {r.website
                      ? <Link href={r.website} isExternal size="sm">site</Link>
                      : <span className="text-default-400">—</span>}
                  </TableCell>
                  <TableCell>
                    {r.rating
                      ? <Chip size="sm" variant="flat" color="warning">★ {r.rating}</Chip>
                      : <span className="text-default-400">—</span>}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          <div className="pt-3 shrink-0 text-small text-default-500">
            <b className="text-foreground">{visiveis.length.toLocaleString('pt-BR')}</b>
            {filtrarMapa && centro ? ` no raio · ${total} coletadas no total` : ` empresas coletadas`}
          </div>
        </div>
      </div>
    </div>
  )
}
