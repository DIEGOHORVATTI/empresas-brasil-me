// Serviço WhatsApp via Baileys. Loga uma conta (QR) e checa se números existem.
// Rodar:  cd mailer && node whatsapp.mjs   (fica ouvindo na porta 3001)
// A sessão persiste em mailer/wa_auth/ — loga o QR só na primeira vez.

import { createServer } from 'node:http'
import { parse } from 'node:url'
import makeWASocket, {
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  DisconnectReason,
  Browsers,
} from '@whiskeysockets/baileys'
import qrcode from 'qrcode'
import pino from 'pino'

const PORT = 3001
const logger = pino({ level: 'silent' })

let sock = null
let currentQR = null // data URL do QR pendente (null quando já logado)
let connected = false

async function start() {
  const { version } = await fetchLatestBaileysVersion() // sem isso o WA recusa a conexão
  const { state, saveCreds } = await useMultiFileAuthState('wa_auth')
  sock = makeWASocket({ version, auth: state, logger, browser: Browsers.ubuntu('Chrome') })

  sock.ev.on('creds.update', saveCreds)
  sock.ev.on('connection.update', async (u) => {
    const { connection, lastDisconnect, qr } = u
    if (qr) currentQR = await qrcode.toDataURL(qr)
    if (connection === 'open') {
      connected = true
      currentQR = null
    }
    if (connection === 'close') {
      connected = false
      const code = lastDisconnect?.error?.output?.statusCode
      if (code !== DisconnectReason.loggedOut) start() // reconecta, exceto se deslogado
    }
  })
}

// Normaliza para E.164 brasileiro: 55 + DDD + número (só dígitos).
function normalize(n) {
  let d = String(n).replace(/\D/g, '')
  if (!d.startsWith('55')) d = '55' + d
  return d
}

async function check(number) {
  if (!connected || !sock) return { error: 'whatsapp não conectado' }
  const [res] = await sock.onWhatsApp(normalize(number))
  return { exists: !!res?.exists }
}

createServer(async (req, res) => {
  const { pathname, query } = parse(req.url, true)
  res.setHeader('Content-Type', 'application/json')
  try {
    if (pathname === '/status') {
      return res.end(JSON.stringify({ connected, qr: currentQR }))
    }
    if (pathname === '/check') {
      const out = await check(query.n)
      return res.end(JSON.stringify(out))
    }
    res.statusCode = 404
    res.end(JSON.stringify({ error: 'not found' }))
  } catch (e) {
    res.statusCode = 500
    res.end(JSON.stringify({ error: String(e?.message || e) }))
  }
}).listen(PORT, () => console.log(`whatsapp service on :${PORT}`))

start()
