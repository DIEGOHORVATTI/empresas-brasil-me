import { NICHOS } from '../nichos.js'

// Mapa divisão CNAE (2 dígitos) -> slug do nicho, montado a partir de nichos.js.
const MAP = {}
for (const [slug, n] of Object.entries(NICHOS)) {
  for (const p of n.prefixos) MAP[p] = slug
}

// Recebe o CNAE (7 dígitos) e devolve o slug do nicho.
export function nichoDoCnae(cnae) {
  const div = String(cnae ?? '').padStart(7, '0').slice(0, 2)
  if (MAP[div]) return MAP[div]
  const n = Number(div)
  if (n >= 10 && n <= 33) return 'industria' // indústria de transformação
  return 'geral'
}
