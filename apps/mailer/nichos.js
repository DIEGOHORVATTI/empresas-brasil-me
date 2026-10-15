// Fonte única das copies: ../nichos.json (compartilhado com o backend Python).
import data from '../nichos.json' with { type: 'json' }

export const NICHOS = data.nichos
export const ASSUNTOS = Object.fromEntries(
  Object.entries(data.nichos).map(([slug, n]) => [slug, n.assunto]),
)
export const ASSINATURA = data.assinatura
export const OPT_OUT = data.opt_out
