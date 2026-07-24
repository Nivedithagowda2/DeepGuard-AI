import { useState } from 'react'
import VerifyPage from './VerifyPage.jsx'
import SupervisorDashboard from './SupervisorDashboard.jsx'

export default function App() {
  const [tab, setTab] = useState('verify')

  return (
    <div>
      <nav
        style={{
          display: 'flex',
          justifyContent: 'center',
          gap: 12,
          padding: 16,
          borderBottom: '1px solid #ddd',
        }}
      >
        <TabButton active={tab === 'verify'} onClick={() => setTab('verify')}>
          Verification
        </TabButton>
        <TabButton active={tab === 'supervisor'} onClick={() => setTab('supervisor')}>
          Supervisor Dashboard
        </TabButton>
      </nav>

      {tab === 'verify' && <VerifyPage />}
      {tab === 'supervisor' && <SupervisorDashboard />}
    </div>
  )
}

function TabButton({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '8px 20px',
        borderRadius: 8,
        border: 'none',
        background: active ? '#2563eb' : '#e5e7eb',
        color: active ? 'white' : '#333',
        cursor: 'pointer',
        fontWeight: active ? 'bold' : 'normal',
      }}
    >
      {children}
    </button>
  )
}
