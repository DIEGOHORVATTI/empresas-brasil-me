import React from 'react'
import { Body, Container, Head, Html, Link, Preview, Text } from '@react-email/components'
import { ASSINATURA, OPT_OUT } from '../nichos.js'

// Visual de email pessoal comum: fonte padrão, sem cor, sem card, sem botão.
// A assinatura e a linha de opt-out são iguais em todos os modelos.
const body = {
  background: '#ffffff',
  margin: 0,
  fontFamily: 'Arial, Helvetica, sans-serif',
  color: '#222222',
  fontSize: '15px',
  lineHeight: '1.55',
}
const wrap = { maxWidth: '600px', margin: '0 auto', padding: '20px' }
const p = { margin: '0 0 14px' }
const sig = { ...p, margin: '18px 0 0' }
const optout = { margin: '22px 0 0', fontSize: '13px', color: '#888888' }

export function PlainEmail({ preview, children, remetente = 'Diego Horvatti' }) {
  return (
    <Html lang="pt-BR">
      <Head />
      {preview ? <Preview>{preview}</Preview> : null}
      <Body style={body}>
        <Container style={wrap}>
          {children}
          <Text style={sig}>
            {ASSINATURA.split('\n').map((linha, i) => (
              <span key={i}>
                {linha === 'horvatti.com'
                  ? <Link href="https://horvatti.com" style={{ color: '#1a5fb4' }}>horvatti.com</Link>
                  : linha}
                <br />
              </span>
            ))}
          </Text>
          <Text style={optout}>{OPT_OUT}</Text>
        </Container>
      </Body>
    </Html>
  )
}

export const par = p
