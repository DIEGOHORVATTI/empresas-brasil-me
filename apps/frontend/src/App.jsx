import { useState } from 'react'
import { Tabs, Tab } from '@heroui/react'
import Empresas from './Empresas'
import Maps from './Maps'

export default function App() {
  const [aba, setAba] = useState('empresas')
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <header className="px-6 pt-3 shrink-0 flex items-center gap-4 border-b border-divider">
        <span className="font-semibold text-small">Empresas Brasil</span>
        <Tabs selectedKey={aba} onSelectionChange={setAba} variant="underlined" size="sm">
          <Tab key="empresas" title="Empresas (RF)" />
          <Tab key="maps" title="Buscar no Maps" />
        </Tabs>
      </header>
      {aba === 'empresas' ? <Empresas /> : <Maps />}
    </div>
  )
}
