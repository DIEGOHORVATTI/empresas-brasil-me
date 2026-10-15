// Motor de campanha (dry-run). Puxa leads da API pelo mesmo filtro do frontend,
// roteia por nicho, aplica nome limpo e gera preview pra revisão. NÃO envia.
//
// Uso (de dentro de mailer/):
//   npm run campanha -- "situacao=02&data_inicio_max=20260703&tem_email=true"
//   npm run campanha -- "<url ou query>" --amostra=30 --template=saude
//
// --template força um nicho pra todos; sem ele, cada lead cai no nicho do CNAE.

import React from 'react'
import { render } from '@react-email/components'
import { mkdirSync, writeFileSync } from 'node:fs'
import Nicho from './nicho.jsx'
import { nichoDoCnae } from './lib/routing.mjs'
import { nomeEmpresa, primeiroNome } from './lib/nome.mjs'
import { ASSUNTOS } from './nichos.js'

const API = process.env.API || 'http://localhost:8010'
const args = process.argv.slice(2)
const flag = (name) => (args.find((a) => a.startsWith(`--${name}=`)) || '').split('=')[1]

const query = (args.find((a) => !a.startsWith('--')) || 'situacao=02&tem_email=true')
  .replace(/^https?:\/\/[^?]*\??/, '') // aceita a URL inteira ou só a query
const amostra = Number(flag('amostra')) || 25
const forceTemplate = flag('template') || null

const fillAssunto = (t, nome) => t.replaceAll('{nome}', nome || 'sua empresa')
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

const res = await fetch(`${API}/api/empresas?${query}&limit=${amostra}&offset=0`)
if (!res.ok) {
  console.error(`API respondeu ${res.status}. O servidor (${API}) está no ar?`)
  process.exit(1)
}
const { results } = await res.json()

mkdirSync('out', { recursive: true })
const blocks = []
const csv = ['cnpj,email,nicho,assunto,nome']
const dist = {}

for (const r of results) {
  const nome = nomeEmpresa(r.razao_social || '', r.nome_fantasia || '')
  const slug = forceTemplate || nichoDoCnae(r.cnae_fiscal_principal)
  const assunto = fillAssunto(ASSUNTOS[slug] || ASSUNTOS.geral, primeiroNome(nome))
  const html = await render(
    <Nicho slug={slug} razaoSocial={r.razao_social || ''} nomeFantasia={r.nome_fantasia || ''} />,
  )
  dist[slug] = (dist[slug] || 0) + 1
  const cnpj = `${r.cnpj_basico}${r.cnpj_ordem}${r.cnpj_dv}`
  blocks.push(`<div style="margin:20px;max-width:640px">
    <div style="font:12px monospace;color:#666;margin-bottom:4px">
      ${r.email} · nicho: <b>${slug}</b> · assunto: <b>${esc(assunto)}</b></div>
    <iframe srcdoc="${esc(html)}" style="width:100%;height:420px;border:1px solid #ccc;background:#fff"></iframe>
  </div>`)
  csv.push([cnpj, r.email, slug, JSON.stringify(assunto), JSON.stringify(nome || '')].join(','))
}

writeFileSync('out/campanha.html', `<html><body style="background:#eee;font-family:Arial">${blocks.join('')}</body></html>`)
writeFileSync('out/campanha.csv', csv.join('\n'))

console.log(`Dry-run: ${results.length} emails gerados.`)
console.log('  out/campanha.html  (preview visual)')
console.log('  out/campanha.csv   (destinatario, nicho, assunto)')
console.log('Distribuição por nicho:', dist)
