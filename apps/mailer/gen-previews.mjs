// One-shot: gera um arquivo de preview por nicho em emails/. Rode: node gen-previews.mjs
import { writeFileSync } from 'node:fs'
import { NICHOS } from './nichos.js'

for (const slug of Object.keys(NICHOS)) {
  writeFileSync(
    `emails/nicho-${slug}.jsx`,
    `import Nicho from '../nicho.jsx'\nexport default function P() { return <Nicho slug="${slug}" /> }\n`,
  )
}
console.log('previews gerados:', Object.keys(NICHOS).length)
