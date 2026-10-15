// Limpa o nome da empresa vindo cru da Receita (tudo maiúsculo, com LTDA/ME,
// dígitos de MEI, etc) pra usar na saudação. Retorna '' se não sobrar nome bom.

const CONECT = new Set(['de', 'da', 'do', 'das', 'dos', 'e'])
const SUFIXOS = new Set(['ltda', 'me', 'epp', 'eireli', 'eirl', 'mei', 'ss'])

export function nomeEmpresa(razaoSocial = '', nomeFantasia = '') {
  // Razão social primeiro: no MEI é o nome do dono (pessoa), o mais pessoal.
  let s = (razaoSocial || nomeFantasia || '').trim()
  if (!s) return ''
  s = s
    .replace(/\bs[./]?a\b/gi, ' ') // S/A, S.A, SA
    .replace(/[-–—]/g, ' ')
    .replace(/\d[\d./-]*/g, ' ') // números e CPF/CNPJ do MEI (ex: 67.305.091)
    .replace(/\s+/g, ' ')
    .trim()
  let tk = s.split(' ').filter(Boolean)
  // remove sufixos jurídicos no fim (LTDA, ME, EPP...)
  while (tk.length > 1 && SUFIXOS.has(tk[tk.length - 1].toLowerCase().replace(/\./g, ''))) {
    tk.pop()
  }
  if (!tk.length) return ''
  return tk
    .map((w, i) => {
      const low = w.toLowerCase()
      return i > 0 && CONECT.has(low) ? low : low.charAt(0).toUpperCase() + low.slice(1)
    })
    .join(' ')
}

// Primeiro nome, pra saudação soar como email de pessoa ("Oi, Lucas").
export function primeiroNome(nome) {
  return nome ? nome.split(' ')[0] : ''
}

// Saudação que personaliza quando há nome e não quebra quando não há.
export function saudacao(nome) {
  return nome ? `Oi, ${nome}` : 'Oi'
}
