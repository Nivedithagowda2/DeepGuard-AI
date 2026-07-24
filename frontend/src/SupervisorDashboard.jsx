import { useEffect, useState, useRef, useCallback } from 'react'
import { fetchHistory } from './api.js'

const WS_URL = 'ws://localhost:8000/ws/alerts'
const RECONNECT_DELAY_MS = 2000

export default function SupervisorDashboard() {
  const [records, setRecords] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)

  // Load existing history once on mount (the "backlog") - after this,
  // new entries arrive instantly via WebSocket push, not polling.
  const loadInitialHistory = useCallback(async () => {
    try {
      const data = await fetchHistory(50)
      setRecords(data.records)
      setError(null)
    } catch (err) {
      setError('Could not reach the backend. Is dashboard.py running on port 8000?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadInitialHistory()

    let cancelled = false

    function connectWebSocket() {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          if (payload.type === 'new_verification') {
            const record = {
              ...payload.record,
              timestamp: new Date().toISOString(),
            }
            setRecords((prev) => [record, ...prev].slice(0, 50))
          }
        } catch (err) {
          console.warn('Could not parse WebSocket message:', err)
        }
      }

      ws.onclose = () => {
        setConnected(false)
        // Auto-reconnect - the backend may restart during development (--reload)
        if (!cancelled) {
          setTimeout(connectWebSocket, RECONNECT_DELAY_MS)
        }
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connectWebSocket()

    return () => {
      cancelled = true
      wsRef.current?.close()
    }
  }, [loadInitialHistory])

  return (
    <div style={{ maxWidth: 700, margin: '0 auto', padding: 24, fontFamily: 'sans-serif' }}>
      <h1 style={{ textAlign: 'center' }}>Supervisor Dashboard</h1>
      <p style={{ textAlign: 'center', color: '#555' }}>
        Simulates the mobile alert app a security supervisor would monitor
      </p>

      <div style={{ textAlign: 'center', marginBottom: 12, fontSize: 13 }}>
        <span
          style={{
            display: 'inline-block',
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: connected ? '#1a9d4b' : '#c62828',
            marginRight: 6,
          }}
        />
        {connected ? 'Live - connected for instant alerts' : 'Reconnecting...'}
      </div>

      {loading && <p style={{ textAlign: 'center' }}>Loading history...</p>}
      {error && <p style={{ color: '#c62828', textAlign: 'center' }}>{error}</p>}

      {!loading && records.length === 0 && (
        <p style={{ textAlign: 'center', color: '#888' }}>
          No verification attempts logged yet. Try the main Verification page first.
        </p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 16 }}>
        {records.map((record, idx) => {
          const isHighRisk = record.status === 'HIGH RISK'
          return (
            <div
              key={record.id ?? idx}
              style={{
                padding: 14,
                borderRadius: 10,
                border: `2px solid ${isHighRisk ? '#c62828' : '#1a9d4b'}`,
                background: isHighRisk ? '#fdecea' : '#eafaf0',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <strong>{isHighRisk ? '🔴' : '🟢'} {record.status}</strong>
                <div style={{ fontSize: 13, color: '#555' }}>
                  {new Date(record.timestamp).toLocaleString()}
                </div>
                <div style={{ fontSize: 13, color: '#555' }}>{record.reasons}</div>
                {record.processing_time_ms != null && (
                  <div style={{ fontSize: 12, color: '#888' }}>
                    Processed in {record.processing_time_ms}ms/frame
                  </div>
                )}
              </div>
              <div style={{ fontSize: 22, fontWeight: 'bold' }}>
                {record.risk_score}%
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
