import { useEffect, useRef, useState } from 'react'
import {
  Card, CardBody, Input, Textarea, Select, SelectItem, Autocomplete, AutocompleteItem,
  DatePicker, Switch, Button, Table, TableHeader, TableColumn, TableBody,
  TableRow, TableCell, Chip, Link, Spinner, Pagination, Tooltip,
  Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, useDisclosure,
  Accordion, AccordionItem, Popover, PopoverTrigger, PopoverContent, Badge, Divider,
} from '@heroui/react'
import { today, getLocalTimeZone, CalendarDate } from '@internationalized/date'

const LIMIT = 50
const SITUACOES = [
  { key: '02', label: 'Ativa' }, { key: '03', label: 'Suspensa' },
  { key: '04', label: 'Inapta' }, { key: '08', label: 'Baixada' },
]
const PORTES = [
  { key: '01', label: 'ME' }, { key: '03', label: 'EPP' }, { key: '05', label: 'Demais' },
]
const MEIS = [{ k: '', v: 'Todos' }, { k: 'S', v: 'Sim' }, { k: 'N', v: 'Não' }]
const NICHOS_OPTS = [
  { key: 'imobiliario', label: 'Imobiliário' }, { key: 'construcao', label: 'Construção' },
  { key: 'saude', label: 'Saúde' }, { key: 'veiculos', label: 'Veículos' },
  { key: 'contabilidade', label: 'Contabilidade/Jurídico' }, { key: 'industria', label: 'Indústria' },
  { key: 'atacado', label: 'Atacado' }, { key: 'servicos', label: 'Serviços/Projetos' },
  { key: 'educacao', label: 'Educação' }, { key: 'transporte', label: 'Transporte' },
]
const CATEGORIAS = [
  ['nicho', 'Nicho'], ['uf', 'UF'], ['situacao', 'Situação'], ['porte', 'Porte'], ['mei', 'MEI'],
  ['cnae', 'CNAE'], ['abertura', 'Abertura'], ['capital', 'Capital social'], ['email', 'Com e-mail'],
]
const PORTE_LABEL = { '00': 'N/I', '01': 'ME', '03': 'EPP', '05': 'Demais' }
const SIT_COLOR = { '02': 'success', '03': 'warning', '04': 'default', '08': 'danger' }
const SIT_LABEL = Object.fromEntries(SITUACOES.map((s) => [s.key, s.label]))

const fmtDate = (s) => (s && s.length === 8 ? `${s.slice(6, 8)}/${s.slice(4, 6)}/${s.slice(0, 4)}` : s || '—')
const fmtCnpj = (r) =>
  `${r.cnpj_basico}${r.cnpj_ordem}${r.cnpj_dv}`.replace(
    /(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5')
const toYmd = (d) => (d ? `${d.year}${String(d.month).padStart(2, '0')}${String(d.day).padStart(2, '0')}` : '')
const BRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
const fmtCapital = (v) => {
  const n = Number(String(v ?? '').replace(',', '.'))
  return n > 0 ? BRL.format(n) : '—'
}
const soDigitos = (v) => String(v ?? '').replace(/\D/g, '')
const maskMilhar = (v) => {
  const n = soDigitos(v)
  return n ? Number(n).toLocaleString('pt-BR') : ''
}
const fromYmd = (s) =>
  s && s.length === 8 ? new CalendarDate(+s.slice(0, 4), +s.slice(4, 6), +s.slice(6, 8)) : null

// MultiSelect com autocomplete: digita p/ filtrar, seleciona vira chip.
function MultiAutocomplete({ label, options, selected, onChange, placeholder }) {
  const [input, setInput] = useState('')
  const add = (key) => {
    if (key && !selected.includes(key)) onChange([...selected, key])
    setInput('')
  }
  const chipOf = (k) => (options.find((o) => o.key === k) || {}).chip
    || (options.find((o) => o.key === k) || {}).label || k
  // Filtramos aqui porque com inputValue controlado o HeroUI não filtra sozinho.
  const q = input.trim().toLowerCase()
  const items = q
    ? options.filter((o) => (o.text || o.label).toLowerCase().includes(q))
    : options
  return (
    <div className="flex flex-col gap-1.5">
      <Autocomplete
        label={label} size="sm" placeholder={placeholder} items={items}
        inputValue={input} onInputChange={setInput} selectedKey={null}
        onSelectionChange={add} isVirtualized menuTrigger="input"
      >
        {(o) => (
          <AutocompleteItem key={o.key} textValue={o.text || o.label}>{o.label}</AutocompleteItem>
        )}
      </Autocomplete>
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {selected.map((k) => (
            <Chip key={k} size="sm" variant="flat" color="primary" onClose={() =>
              onChange(selected.filter((x) => x !== k))}>{chipOf(k)}</Chip>
          ))}
        </div>
      )}
    </div>
  )
}

// Estado inicial vindo da URL, pra sobreviver ao F5.
const URL0 = new URLSearchParams(window.location.search)
const HAS_URL = URL0.toString().length > 0

export default function Empresas() {
  const [ufOpts, setUfOpts] = useState([])
  const [cnaeOpts, setCnaeOpts] = useState([])
  const [uf, setUf] = useState(() => URL0.getAll('uf'))
  const [situacao, setSituacao] = useState(() =>
    URL0.has('situacao') ? URL0.getAll('situacao') : HAS_URL ? [] : ['02'])
  const [porte, setPorte] = useState(() => URL0.getAll('porte'))
  const [cnae, setCnae] = useState(() => URL0.getAll('cnae'))
  const [mei, setMei] = useState(URL0.get('mei') || '')
  const [temEmail, setTemEmail] = useState(URL0.get('tem_email') !== 'false')
  const [dMin, setDMin] = useState(() =>
    URL0.has('data_inicio_min')
      ? fromYmd(URL0.get('data_inicio_min'))
      : HAS_URL ? null : today(getLocalTimeZone()).subtract({ days: 30 }))
  const [dMax, setDMax] = useState(() =>
    URL0.has('data_inicio_max')
      ? fromYmd(URL0.get('data_inicio_max'))
      : HAS_URL ? null : today(getLocalTimeZone()))
  const [capMin, setCapMin] = useState(() =>
    URL0.has('capital_min') ? URL0.get('capital_min') : HAS_URL ? '' : '10000')
  const [capMax, setCapMax] = useState(URL0.get('capital_max') || '')
  const [nicho, setNicho] = useState(() =>
    URL0.has('nicho') ? URL0.getAll('nicho') : HAS_URL ? [] : NICHOS_OPTS.map((n) => n.key))
  const [sortDescriptor, setSortDescriptor] = useState(() => ({
    column: URL0.get('sort') || 'data_inicio_atividade',
    direction: URL0.get('order') === 'asc' ? 'ascending' : 'descending',
  }))

  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(Number(URL0.get('page')) || 1)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(new Set())
  const [porPagina, setPorPagina] = useState(Number(URL0.get('por_pagina')) || LIMIT)

  const totalPaginas = Math.max(1, Math.ceil(total / porPagina))

  // --- Campanha (revisar e enviar) ---
  const { isOpen, onOpen, onClose } = useDisclosure()
  const [emails, setEmails] = useState([])
  const [enviando, setEnviando] = useState(false)
  const [resultados, setResultados] = useState(null)
  const [brevoCfg, setBrevoCfg] = useState({ ok: true, msg: '' })
  const stats2 = useDisclosure()
  const modelosDisc = useDisclosure()
  const [modelos, setModelos] = useState([])
  const abrirModelos = () => {
    if (!modelos.length) fetch('/api/campanha/modelos').then((r) => r.json()).then(setModelos)
    modelosDisc.onOpen()
  }
  const [stats, setStats] = useState({ hoje: 0, total: 0, limite_dia: 300, enviados: [] })
  const carregarStats = () =>
    fetch('/api/campanha/stats').then((r) => r.json()).then(setStats)

  // --- WhatsApp (vincular via QR + verificar números) ---
  const waDisc = useDisclosure()
  const [wa, setWa] = useState({ connected: false, qr: null })
  const [waCheck, setWaCheck] = useState({}) // cnpj -> 'loading' | true | false | 'erro'
  const carregarWaStatus = () =>
    fetch('/api/whatsapp/status').then((r) => r.json()).then(setWa).catch(() => {})
  useEffect(() => {
    if (!waDisc.isOpen || wa.connected) return
    const id = setInterval(carregarWaStatus, 2000) // poll do QR/conexão enquanto o modal está aberto
    return () => clearInterval(id)
  }, [waDisc.isOpen, wa.connected])
  const verificarWhats = (r) => {
    const key = fmtCnpj(r)
    setWaCheck((s) => ({ ...s, [key]: 'loading' }))
    fetch(`/api/whatsapp/check?ddd=${r.ddd_1}&telefone=${r.telefone_1}`)
      .then((res) => res.json())
      .then((d) => setWaCheck((s) => ({ ...s, [key]: d.error ? 'erro' : !!d.exists })))
      .catch(() => setWaCheck((s) => ({ ...s, [key]: 'erro' })))
  }

  useEffect(() => {
    fetch('/api/campanha/config').then((r) => r.json()).then(setBrevoCfg)
    carregarStats()
    carregarWaStatus()
  }, [])

  const leadsSelecionados = () =>
    rows.filter((r) => selected === 'all' || selected.has(fmtCnpj(r)))

  const abrirCampanha = () => {
    setResultados(null)
    const leads = leadsSelecionados().map((r) => ({
      cnpj: fmtCnpj(r).replace(/\D/g, ''),
      email: r.email,
      razao_social: r.razao_social,
      nome_fantasia: r.nome_fantasia,
      cnae_fiscal_principal: r.cnae_fiscal_principal,
    }))
    fetch('/api/campanha/preview', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(leads),
    }).then((r) => r.json()).then(setEmails)
    onOpen()
  }

  const editarEmail = (i, campo, valor) =>
    setEmails((prev) => prev.map((e, idx) => (idx === i ? { ...e, [campo]: valor } : e)))

  const enviarCampanha = () => {
    setEnviando(true)
    fetch('/api/campanha/enviar', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(emails),
    }).then((r) => r.json()).then((d) => {
      setResultados(d)
      setEnviando(false)
      if (!d.erro) { setSelected(new Set()); search(page); carregarStats() }
    })
  }

  const nSelecionados = selected === 'all' ? rows.length : selected.size

  useEffect(() => {
    fetch('/api/ufs').then((r) => r.json())
      .then((us) => setUfOpts(us.map((u) => ({ key: u, label: u }))))
    fetch('/api/cnaes').then((r) => r.json())
      .then((cs) => setCnaeOpts(cs.map((c) => ({
        key: c.codigo,
        label: `${c.codigo} — ${c.descricao}`,
        text: `${c.codigo} ${c.descricao}`,
        chip: c.codigo,
      }))))
  }, [])

  const search = (p = 1, sd = sortDescriptor, pp = porPagina) => {
    setLoading(true); setPage(p)
    const f = new URLSearchParams()
    uf.forEach((v) => f.append('uf', v))
    situacao.forEach((v) => f.append('situacao', v))
    porte.forEach((v) => f.append('porte', v))
    cnae.forEach((v) => f.append('cnae', v))
    if (mei) f.set('mei', mei)
    if (dMin) f.set('data_inicio_min', toYmd(dMin))
    if (dMax) f.set('data_inicio_max', toYmd(dMax))
    if (capMin) f.set('capital_min', capMin)
    if (capMax) f.set('capital_max', capMax)
    nicho.forEach((v) => f.append('nicho', v))
    f.set('tem_email', temEmail)
    f.set('sort', sd.column)
    f.set('order', sd.direction === 'ascending' ? 'asc' : 'desc')

    // reflete os filtros na URL (sobrevive ao F5), sem limit/offset
    const url = new URLSearchParams(f)
    if (p > 1) url.set('page', p)
    if (pp !== LIMIT) url.set('por_pagina', pp)
    window.history.replaceState(null, '', url.toString() ? '?' + url : window.location.pathname)

    f.set('limit', pp); f.set('offset', (p - 1) * pp)
    fetch('/api/empresas?' + f)
      .then((r) => r.json())
      .then((d) => { setRows(d.results); setTotal(d.total ?? 0); setLoading(false) })
  }
  const onSort = (sd) => { setSortDescriptor(sd); search(1, sd) }
  const mudarPorPagina = (v) => { const n = Number(v) || LIMIT; setPorPagina(n); search(1, sortDescriptor, n) }
  useEffect(() => { search(Number(URL0.get('page')) || 1) }, [])

  const filtros = useDisclosure()
  const [filtroAtivo, setFiltroAtivo] = useState('uf')
  const snap = useRef({})
  const nFiltros = uf.length + situacao.length + porte.length + cnae.length + (nicho.length ? 1 : 0)
    + (mei ? 1 : 0) + (dMin ? 1 : 0) + (dMax ? 1 : 0) + (capMin ? 1 : 0) + (capMax ? 1 : 0)

  const temValor = {
    nicho: nicho.length > 0, uf: uf.length > 0, situacao: situacao.length > 0, porte: porte.length > 0,
    mei: !!mei, cnae: cnae.length > 0, abertura: !!(dMin || dMax),
    capital: !!(capMin || capMax), email: temEmail,
  }
  const estadoFiltros = () => ({ uf, situacao, porte, cnae, nicho, mei, dMin, dMax, capMin, capMax, temEmail })
  const restaurarFiltros = () => {
    const s = snap.current
    setUf(s.uf); setSituacao(s.situacao); setPorte(s.porte); setCnae(s.cnae); setNicho(s.nicho); setMei(s.mei)
    setDMin(s.dMin); setDMax(s.dMax); setCapMin(s.capMin); setCapMax(s.capMax); setTemEmail(s.temEmail)
  }
  const onFiltrosChange = (open) => {
    if (open) { snap.current = estadoFiltros(); filtros.onOpen() }
    else { restaurarFiltros(); filtros.onClose() } // fechou por fora/esc = cancela
  }
  const cancelarFiltros = () => { restaurarFiltros(); filtros.onClose() }
  const aplicarFiltros = () => { search(1); filtros.onClose() }

  // Buscar após remover um chip (o useEffect lê o estado já atualizado).
  const [buscarTick, setBuscarTick] = useState(0)
  useEffect(() => { if (buscarTick) search(1) }, [buscarTick]) // eslint-disable-line
  const removerFiltro = (tipo) => {
    ({
      uf: () => setUf([]), situacao: () => setSituacao([]), porte: () => setPorte([]),
      mei: () => setMei(''), cnae: () => setCnae([]),
      abertura: () => { setDMin(null); setDMax(null) },
      capital: () => { setCapMin(''); setCapMax('') },
      email: () => setTemEmail(false), nicho: () => setNicho([]),
    })[tipo]?.()
    setBuscarTick((t) => t + 1)
  }

  const fmtCal = (d) => (d ? `${String(d.day).padStart(2, '0')}/${String(d.month).padStart(2, '0')}/${d.year}` : '…')
  const chipsAtivos = [
    nicho.length && { tipo: 'nicho', label: nicho.length === NICHOS_OPTS.length ? 'Nicho: todos (ticket alto)' : `Nicho: ${nicho.length} selec.` },
    uf.length && { tipo: 'uf', label: `UF: ${uf.join(', ')}` },
    situacao.length && { tipo: 'situacao', label: `Situação: ${situacao.map((s) => SIT_LABEL[s] || s).join(', ')}` },
    porte.length && { tipo: 'porte', label: `Porte: ${porte.map((p) => PORTE_LABEL[p] || p).join(', ')}` },
    mei && { tipo: 'mei', label: `MEI: ${mei === 'S' ? 'Sim' : 'Não'}` },
    cnae.length && { tipo: 'cnae', label: `CNAE: ${cnae.length > 2 ? `${cnae.length} selecionados` : cnae.join(', ')}` },
    (dMin || dMax) && { tipo: 'abertura', label: `Abertura: ${fmtCal(dMin)} a ${fmtCal(dMax)}` },
    (capMin || capMax) && { tipo: 'capital', label: `Capital: R$ ${maskMilhar(capMin) || '0'} a ${capMax ? 'R$ ' + maskMilhar(capMax) : '∞'}` },
    temEmail && { tipo: 'email', label: 'Com e-mail' },
  ].filter(Boolean)

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
      <div className="px-6 pt-4 pb-3 shrink-0">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 flex-wrap min-w-0">
            {chipsAtivos.map((c) => (
              <Chip key={c.tipo} size="sm" variant="flat" color="primary"
                onClose={() => removerFiltro(c.tipo)}>
                {c.label}
              </Chip>
            ))}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button size="sm" variant="flat" onPress={abrirModelos}>
              ✉️ Modelos
            </Button>
            <Button size="sm" variant="flat"
              color={wa.connected ? 'success' : 'default'}
              onPress={() => { carregarWaStatus(); waDisc.onOpen() }}>
              {wa.connected ? '🟢' : '⚪'} WhatsApp
            </Button>
            <Popover isOpen={filtros.isOpen} onOpenChange={onFiltrosChange}
              placement="bottom-end" showArrow
              shouldCloseOnInteractOutside={(el) =>
                !el.closest('[data-slot="calendar"],[data-slot="content"],[role="listbox"],[role="dialog"],[role="grid"],[role="application"]')}>
              <PopoverTrigger>
                <Button variant="flat">
                  <Badge color="primary" content={nFiltros} isInvisible={nFiltros === 0}
                    shape="circle" size="sm">
                    <span className="pr-1">Filtros</span>
                  </Badge>
                </Button>
              </PopoverTrigger>
              <PopoverContent className="p-0 w-[92vw] max-w-[520px] bg-content1">
                <div className="flex w-full min-h-[260px] rounded-large overflow-hidden">
                  {/* menu de filtros (30%) */}
                  <div className="w-[30%] shrink-0 border-r border-divider py-2 bg-default-50">
                    {CATEGORIAS.map(([key, label]) => (
                      <button key={key} onClick={() => setFiltroAtivo(key)}
                        className={`w-full text-left px-4 py-2.5 text-small flex items-center justify-between
                          ${filtroAtivo === key
                            ? 'bg-content1 font-medium border-l-2 border-primary'
                            : 'text-default-600 hover:bg-default-100 border-l-2 border-transparent'}`}>
                        {label}
                        {temValor[key] && <span className="w-1.5 h-1.5 rounded-full bg-primary" />}
                      </button>
                    ))}
                  </div>
                  {/* detalhe do filtro (70%) */}
                  <div className="w-[70%] p-4">
                    {filtroAtivo === 'nicho' && (
                      <MultiAutocomplete label="Nicho (ticket alto)" options={NICHOS_OPTS}
                        selected={nicho} onChange={setNicho} placeholder="Todos os nichos" />
                    )}
                    {filtroAtivo === 'uf' && (
                      <MultiAutocomplete label="UF" options={ufOpts} selected={uf}
                        onChange={setUf} placeholder="Todas" />
                    )}
                    {filtroAtivo === 'situacao' && (
                      <MultiAutocomplete label="Situação" options={SITUACOES} selected={situacao}
                        onChange={setSituacao} placeholder="Todas" />
                    )}
                    {filtroAtivo === 'porte' && (
                      <MultiAutocomplete label="Porte" options={PORTES} selected={porte}
                        onChange={setPorte} placeholder="Todos" />
                    )}
                    {filtroAtivo === 'mei' && (
                      <Select label="MEI" size="sm" selectedKeys={mei ? [mei] : []}
                        onChange={(e) => setMei(e.target.value)}>
                        {MEIS.map((o) => <SelectItem key={o.k}>{o.v}</SelectItem>)}
                      </Select>
                    )}
                    {filtroAtivo === 'cnae' && (
                      <MultiAutocomplete label="CNAE (código ou descrição)" options={cnaeOpts}
                        selected={cnae} onChange={setCnae} placeholder="ex: 4712 ou 'restaurante'" />
                    )}
                    {filtroAtivo === 'abertura' && (
                      <div className="flex flex-col gap-3">
                        <DatePicker label="Abertura de" size="sm" value={dMin} onChange={setDMin}
                          showMonthAndYearPickers />
                        <DatePicker label="Abertura até" size="sm" value={dMax} onChange={setDMax}
                          showMonthAndYearPickers />
                      </div>
                    )}
                    {filtroAtivo === 'capital' && (
                      <div className="flex flex-col gap-3">
                        <Input label="Capital social de" size="sm" inputMode="numeric" placeholder="0"
                          value={maskMilhar(capMin)} onValueChange={(v) => setCapMin(soDigitos(v))}
                          startContent={<span className="text-default-400 text-small">R$</span>} />
                        <Input label="Capital social até" size="sm" inputMode="numeric" placeholder="sem limite"
                          value={maskMilhar(capMax)} onValueChange={(v) => setCapMax(soDigitos(v))}
                          startContent={<span className="text-default-400 text-small">R$</span>} />
                      </div>
                    )}
                    {filtroAtivo === 'email' && (
                      <Switch isSelected={temEmail} onValueChange={setTemEmail} size="sm">
                        Somente empresas com e-mail
                      </Switch>
                    )}
                  </div>
                </div>
                {/* ações */}
                <div className="flex justify-end gap-2 w-full border-t border-divider p-3">
                  <Button variant="light" size="sm" onPress={cancelarFiltros}>Cancelar</Button>
                  <Button color="primary" size="sm" onPress={aplicarFiltros} isLoading={loading}>
                    Aplicar
                  </Button>
                </div>
              </PopoverContent>
            </Popover>
            <Divider orientation="vertical" className="h-6" />
            <Button size="sm" variant="flat"
              color={stats.hoje >= stats.limite_dia ? 'danger' : 'default'}
              onPress={() => { carregarStats(); stats2.onOpen() }}>
              Enviados hoje: {stats.hoje}/{stats.limite_dia}
            </Button>
            <Button color="primary" size="sm" isDisabled={nSelecionados === 0}
              onPress={abrirCampanha}>
              Revisar e enviar {nSelecionados > 0 ? `(${nSelecionados})` : ''}
            </Button>
          </div>
        </div>
      </div>
      <div className="px-6 pb-4 flex-1 min-h-0 flex flex-col">
        <Table
          aria-label="Empresas"
          isHeaderSticky
          classNames={{ base: 'flex-1 min-h-0 flex flex-col', wrapper: 'flex-1 min-h-0' }}
          selectionMode="multiple"
          selectedKeys={selected}
          onSelectionChange={setSelected}
          sortDescriptor={sortDescriptor}
          onSortChange={onSort}>
          <TableHeader>
            <TableColumn key="razao_social" allowsSorting>RAZÃO SOCIAL</TableColumn>
            <TableColumn key="envio_status" allowsSorting>STATUS</TableColumn>
            <TableColumn key="uf" allowsSorting>UF</TableColumn>
            <TableColumn key="data_inicio_atividade" allowsSorting>ABERTURA</TableColumn>
            <TableColumn key="porte_empresa" allowsSorting>PORTE</TableColumn>
            <TableColumn key="capital_social" allowsSorting>CAPITAL SOCIAL</TableColumn>
            <TableColumn key="situacao_cadastral" allowsSorting>SITUAÇÃO</TableColumn>
            <TableColumn key="cnae">CNAE</TableColumn>
            <TableColumn key="email" allowsSorting>E-MAIL</TableColumn>
            <TableColumn key="telefone">TELEFONE</TableColumn>
          </TableHeader>
          <TableBody
            items={rows}
            isLoading={loading}
            loadingContent={<Spinner label="Carregando…" />}
            emptyContent="Nenhum resultado. Ajuste os filtros — e confirme que o banco foi importado.">
            {(r) => (
              <TableRow key={fmtCnpj(r)}>
                <TableCell className="max-w-[260px] truncate">{r.razao_limpa || r.razao_social || '—'}</TableCell>
                <TableCell>
                  {r.envio_status
                    ? <Tooltip content={`${r.envio_template || ''} · ${r.envio_provider || ''} · ${r.enviado_em || ''}`}>
                        <Chip size="sm" variant="flat" color="success">enviado</Chip>
                      </Tooltip>
                    : <span className="text-default-400">—</span>}
                </TableCell>
                <TableCell>{r.uf}</TableCell>
                <TableCell className="whitespace-nowrap">{fmtDate(r.data_inicio_atividade)}</TableCell>
                <TableCell>{PORTE_LABEL[r.porte_empresa] || '—'}</TableCell>
                <TableCell className="whitespace-nowrap">{fmtCapital(r.capital_social)}</TableCell>
                <TableCell>
                  <Chip size="sm" variant="flat" color={SIT_COLOR[r.situacao_cadastral] || 'default'}>
                    {SIT_LABEL[r.situacao_cadastral] || r.situacao_cadastral}
                  </Chip>
                </TableCell>
                <TableCell className="max-w-[240px]">
                  <Tooltip content={r.cnae_fiscal_principal} placement="top">
                    <span className="line-clamp-2">{r.cnae_desc || r.cnae_fiscal_principal}</span>
                  </Tooltip>
                </TableCell>
                <TableCell>
                  {r.email
                    ? <Link href={`mailto:${r.email}`} size="sm">{r.email.toLowerCase()}</Link>
                    : <span className="text-default-400">—</span>}
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  {r.telefone_1 ? (
                    <div className="flex items-center gap-1.5">
                      <span>{`(${r.ddd_1}) ${r.telefone_1}`}</span>
                      {(() => {
                        const v = waCheck[fmtCnpj(r)]
                        if (v === 'loading') return <Spinner size="sm" />
                        if (v === true) return <span title="Tem WhatsApp" className="text-success">✅</span>
                        if (v === false) return <span title="Não tem WhatsApp" className="text-danger">❌</span>
                        if (v === 'erro') return <span title="Serviço offline">⚠️</span>
                        return (
                          <Tooltip content={wa.connected ? 'Verificar WhatsApp' : 'Vincule o WhatsApp primeiro'}>
                            <Button isIconOnly size="sm" variant="light" radius="full"
                              isDisabled={!wa.connected} onPress={() => verificarWhats(r)}>
                              🔍
                            </Button>
                          </Tooltip>
                        )
                      })()}
                    </div>
                  ) : <span className="text-default-400">—</span>}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        {/* rodapé fixo da grid */}
        <div className="flex items-center justify-between gap-4 pt-3 shrink-0">
          <span className="text-small text-default-500">
            <b className="text-foreground">{total.toLocaleString('pt-BR')}</b> empresas no filtro
            {nSelecionados > 0 && ` · ${nSelecionados} selecionada(s)`}
          </span>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-small text-default-500">
              Por página:
              <Select aria-label="Itens por página" size="sm" className="w-24"
                selectedKeys={[String(porPagina)]}
                onChange={(e) => e.target.value && mudarPorPagina(e.target.value)}>
                {['25', '50', '100', '200'].map((n) => <SelectItem key={n}>{n}</SelectItem>)}
              </Select>
            </div>
            <Pagination isCompact showControls showShadow page={page}
              total={totalPaginas} onChange={(p) => search(p)} />
          </div>
        </div>
      </div>

      <Modal isOpen={waDisc.isOpen} onClose={waDisc.onClose} size="sm">
        <ModalContent>
          <ModalHeader>Vincular WhatsApp</ModalHeader>
          <ModalBody className="items-center text-center pb-6">
            {wa.connected ? (
              <>
                <span className="text-4xl">🟢</span>
                <p className="text-success font-medium">WhatsApp vinculado!</p>
                <p className="text-tiny text-default-500">
                  Já pode verificar os números na lista pelo botão 🔍.
                </p>
              </>
            ) : wa.qr ? (
              <>
                <p className="text-small text-default-500">
                  Abra o WhatsApp no celular → Aparelhos conectados → Conectar aparelho
                  e aponte para o QR.
                </p>
                <img src={wa.qr} alt="QR WhatsApp" className="w-56 h-56" />
              </>
            ) : wa.offline ? (
              <p className="text-danger text-small">
                Serviço offline. Rode <code>cd mailer &amp;&amp; npm run whatsapp</code>.
              </p>
            ) : (
              <><Spinner /><p className="text-tiny text-default-500">Gerando QR…</p></>
            )}
          </ModalBody>
        </ModalContent>
      </Modal>

      <Modal isOpen={isOpen} onClose={onClose} size="3xl" scrollBehavior="inside">
        <ModalContent>
          <ModalHeader className="flex-col items-start gap-1">
            <span>Revisar e enviar {emails.length} email(s)</span>
            {!brevoCfg.ok && (
              <span className="text-tiny text-warning font-normal">
                ⚠ Brevo não configurado: {brevoCfg.msg}
              </span>
            )}
          </ModalHeader>
          <ModalBody>
            {resultados ? (
              <div className="flex flex-col gap-2">
                {resultados.erro && <p className="text-danger">{resultados.erro}</p>}
                {resultados.resultados?.map((r) => (
                  <div key={r.cnpj} className="flex items-center gap-2 text-small">
                    <Chip size="sm" color={r.ok ? 'success' : 'danger'} variant="flat">
                      {r.ok ? 'enviado' : 'erro'}
                    </Chip>
                    <span>{r.email}</span>
                    {!r.ok && <span className="text-default-400">{r.msg}</span>}
                  </div>
                ))}
              </div>
            ) : (
              <Accordion variant="bordered" selectionMode="multiple">
                {emails.map((e, i) => (
                  <AccordionItem key={e.cnpj || i}
                    title={<span className="text-small">{e.email}</span>}
                    subtitle={<span className="text-tiny text-default-400">
                      {e.razao_social} · {e.nicho}</span>}>
                    <div className="flex flex-col gap-3 pb-2">
                      <Input label="Assunto" size="sm" value={e.assunto}
                        onValueChange={(v) => editarEmail(i, 'assunto', v)} />
                      <Textarea label="Corpo" minRows={10} value={e.corpo}
                        onValueChange={(v) => editarEmail(i, 'corpo', v)} />
                    </div>
                  </AccordionItem>
                ))}
              </Accordion>
            )}
          </ModalBody>
          <ModalFooter>
            <Button variant="light" onPress={onClose}>
              {resultados ? 'Fechar' : 'Cancelar'}
            </Button>
            {!resultados && (
              <Button color="primary" isLoading={enviando}
                isDisabled={!brevoCfg.ok || emails.length === 0}
                onPress={enviarCampanha}>
                Enviar {emails.length} email(s) via Brevo
              </Button>
            )}
          </ModalFooter>
        </ModalContent>
      </Modal>

      <Modal isOpen={modelosDisc.isOpen} onClose={modelosDisc.onClose} size="3xl" scrollBehavior="inside">
        <ModalContent>
          <ModalHeader className="flex-col items-start gap-1">
            <span>Modelos de email por nicho</span>
            <span className="text-tiny font-normal text-default-500">
              {modelos.length} modelos · exemplo com "Padaria do João"
            </span>
          </ModalHeader>
          <ModalBody className="pb-6">
            <Accordion variant="bordered" selectionMode="multiple">
              {modelos.map((m) => (
                <AccordionItem key={m.nicho}
                  title={<span className="capitalize text-small">{m.nicho}</span>}
                  subtitle={<span className="text-tiny text-default-400">{m.assunto}</span>}>
                  <pre className="whitespace-pre-wrap font-sans text-small text-default-600 pb-2">
                    {m.corpo}
                  </pre>
                </AccordionItem>
              ))}
            </Accordion>
          </ModalBody>
        </ModalContent>
      </Modal>

      <Modal isOpen={stats2.isOpen} onClose={stats2.onClose} size="2xl" scrollBehavior="inside">
        <ModalContent>
          <ModalHeader className="flex-col items-start gap-1">
            <span>Emails enviados hoje</span>
            <span className="text-tiny font-normal text-default-500">
              {stats.hoje} de {stats.limite_dia} da cota diária · {stats.total.toLocaleString('pt-BR')} no total
            </span>
          </ModalHeader>
          <ModalBody className="pb-6">
            {stats.enviados.length === 0 ? (
              <p className="text-default-500 text-small">Nenhum email enviado hoje ainda.</p>
            ) : (
              <Table aria-label="Enviados hoje" removeWrapper>
                <TableHeader>
                  <TableColumn>HORA</TableColumn>
                  <TableColumn>E-MAIL</TableColumn>
                  <TableColumn>NICHO</TableColumn>
                  <TableColumn>STATUS</TableColumn>
                </TableHeader>
                <TableBody items={stats.enviados}>
                  {(e) => (
                    <TableRow key={e.email + e.enviado_em}>
                      <TableCell className="whitespace-nowrap">{(e.enviado_em || '').slice(11, 16)}</TableCell>
                      <TableCell>{e.email?.toLowerCase()}</TableCell>
                      <TableCell>{e.template}</TableCell>
                      <TableCell>
                        <Chip size="sm" variant="flat"
                          color={e.status === 'enviado' ? 'success' : 'danger'}>
                          {e.status}
                        </Chip>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </ModalBody>
        </ModalContent>
      </Modal>
    </div>
  )
}
