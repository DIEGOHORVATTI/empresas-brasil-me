import React from 'react'
import { Text } from '@react-email/components'
import { PlainEmail, par } from './components/PlainEmail.jsx'
import { NICHOS } from './nichos.js'
import { nomeEmpresa, saudacao, primeiroNome } from './lib/nome.mjs'

// Template único: recebe o slug do nicho + dados do lead e renderiza a copy.
export default function Nicho({
  slug = 'geral',
  razaoSocial = 'EMPRESA EXEMPLO LTDA',
  nomeFantasia = 'Empresa Exemplo',
  cidade = 'São Paulo',
}) {
  const n = NICHOS[slug] || NICHOS.geral
  const nome = nomeEmpresa(razaoSocial, nomeFantasia)
  const fill = (t) =>
    t
      .replaceAll('{saudacao}', saudacao(primeiroNome(nome)))
      .replaceAll('{nome}', nome || 'sua empresa')
      .replaceAll('{cidade}', cidade)
  return (
    <PlainEmail>
      {n.paragrafos.map((t, i) => (
        <Text key={i} style={par}>{fill(t)}</Text>
      ))}
    </PlainEmail>
  )
}
