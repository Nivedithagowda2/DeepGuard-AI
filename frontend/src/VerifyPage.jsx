import { useRef, useState, useEffect, useCallback } from 'react'
import { resetSession, verifyFrame, finalizeVerification } from './api.js'

// Recording configuration - tune these based on your webcam's performance
const TOTAL_FRAMES = 15       // how many frames to capture during the recording window
const FRAME_INTERVAL_MS = 200 // gap between captures (~5 frames/second)
// Total recording time = TOTAL_FRAMES * FRAME_INTERVAL_MS = ~3 seconds

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export default function VerifyPage() {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const [streaming, setStreaming] = useState(false)
  const [result, setResult] = useState(null)
  const [recording, setRecording] = useState(false)
  const [instruction, setInstruction] = useState('')
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true })
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          setStreaming(true)
        }
      } catch (err) {
        // Surface the ACTUAL browser error instead of a generic message -
        // this tells you exactly why the camera failed (permission denied,
        // no camera found, camera already in use by another app, etc.)
        const reason = err && err.name ? err.name : 'UnknownError'
        setError(
          `Could not access webcam (${reason}: ${err?.message || 'no details'}). ` +
          `Check: 1) Windows Settings > Privacy > Camera is allowed for this browser, ` +
          `2) the site's camera permission (click the icon next to the address bar), ` +
          `3) no other app is currently using the camera.`
        )
      }
    }
    startCamera()

    return () => {
      const stream = videoRef.current?.srcObject
      if (stream) {
        stream.getTracks().forEach((track) => track.stop())
      }
    }
  }, [])

  const captureBlob = useCallback(() => {
    return new Promise((resolve) => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!video || !canvas) {
        resolve(null)
        return
      }
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext('2d')
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.9)
    })
  }, [])

  const runVerificationSequence = useCallback(async () => {
    setResult(null)
    setError(null)
    setRecording(true)
    setProgress(0)

    try {
      await resetSession()

      for (let i = 0; i < TOTAL_FRAMES; i++) {
        // Cycle through instructions so the person knows what to do at each stage
        if (i < 5) {
          setInstruction('Look at the camera and blink naturally...')
        } else if (i < 10) {
          setInstruction('Slowly turn your head slightly left, then right...')
        } else {
          setInstruction('Hold still, almost done...')
        }

        const blob = await captureBlob()
        if (blob) {
          try {
            await verifyFrame(blob)
          } catch (frameErr) {
            // Don't abort the whole recording over one dropped frame -
            // just continue; finalize will still work with the frames that
            // did succeed, as long as enough of them came through.
            console.warn('Frame send failed:', frameErr)
          }
        }

        setProgress(Math.round(((i + 1) / TOTAL_FRAMES) * 100))
        await sleep(FRAME_INTERVAL_MS)
      }

      setInstruction('Analyzing...')
      const finalResult = await finalizeVerification()
      setResult(finalResult)
    } catch (err) {
      setError('Could not reach the backend. Is dashboard.py running on port 8000?')
    } finally {
      setRecording(false)
      setInstruction('')
    }
  }, [captureBlob])

  const statusColor =
    result?.status === 'VERIFIED' ? '#1a9d4b' :
    result?.status === 'HIGH RISK' ? '#c62828' :
    '#666'

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: 24, fontFamily: 'sans-serif' }}>
      <h1 style={{ textAlign: 'center' }}>DeepGuard AI</h1>
      <p style={{ textAlign: 'center', color: '#555' }}>
        Decentralized Multimodal Anti-Spoofing Verification
      </p>

      <div style={{ position: 'relative', borderRadius: 12, overflow: 'hidden', background: '#000' }}>
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          style={{ width: '100%', display: 'block', transform: 'scaleX(-1)' }}
        />
        {recording && (
          <div
            style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              background: 'rgba(0,0,0,0.6)',
              color: 'white',
              padding: '10px 14px',
            }}
          >
            <div style={{ fontSize: 14, marginBottom: 6 }}>{instruction}</div>
            <div style={{ background: '#444', borderRadius: 6, height: 6, overflow: 'hidden' }}>
              <div
                style={{
                  width: `${progress}%`,
                  height: '100%',
                  background: '#2563eb',
                  transition: 'width 0.15s linear',
                }}
              />
            </div>
          </div>
        )}
      </div>
      <canvas ref={canvasRef} style={{ display: 'none' }} />

      {error && (
        <p style={{ color: '#c62828', textAlign: 'center', marginTop: 12, fontSize: 14 }}>{error}</p>
      )}

      <div style={{ textAlign: 'center', marginTop: 20 }}>
        <button
          onClick={runVerificationSequence}
          disabled={!streaming || recording}
          style={{
            padding: '12px 32px',
            fontSize: 16,
            borderRadius: 8,
            border: 'none',
            background: '#2563eb',
            color: 'white',
            cursor: streaming && !recording ? 'pointer' : 'not-allowed',
            opacity: recording ? 0.7 : 1,
          }}
        >
          {recording ? 'Recording...' : 'Start Verification'}
        </button>
      </div>

      {result && (
        <div
          style={{
            marginTop: 24,
            padding: 20,
            borderRadius: 12,
            background: statusColor,
            color: 'white',
            textAlign: 'center',
          }}
        >
          <h2 style={{ margin: 0 }}>
            {result.status === 'VERIFIED' && '🟢 VERIFIED'}
            {result.status === 'HIGH RISK' && '🔴 HIGH RISK'}
            {result.status === 'NO FACE DETECTED' && '⚪ NO FACE DETECTED'}
          </h2>
          {result.risk_score !== null && result.risk_score !== undefined && (
            <p style={{ fontSize: 20, margin: '8px 0' }}>Risk: {result.risk_score}%</p>
          )}
          {result.reasons && (
            <p style={{ fontSize: 14, opacity: 0.9 }}>{result.reasons.join(' · ')}</p>
          )}
          {result.processing_time_ms != null && (
            <p style={{ fontSize: 12, opacity: 0.75, marginTop: 4 }}>
              On-device inference: {result.processing_time_ms}ms/frame
            </p>
          )}
          {result.message && <p>{result.message}</p>}
        </div>
      )}
    </div>
  )
}
