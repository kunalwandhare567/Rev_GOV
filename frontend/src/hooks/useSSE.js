/**
 * useSSE — Phase 12 Frontend Hook
 * Connects to the backend SSE stream for real-time application updates.
 * Automatically reconnects on disconnect with exponential backoff.
 *
 * Usage:
 *   const { status, progress, lastEvent } = useSSE(applicationId)
 */
import { useState, useEffect, useRef, useCallback } from 'react'

const SSE_BASE = 'http://localhost:8000/api/v1/stream/applications'
const MAX_RECONNECT_DELAY = 30000  // 30s max backoff
const INITIAL_RECONNECT_DELAY = 2000

export default function useSSE(applicationId) {
  const [status, setStatus] = useState(null)
  const [progress, setProgress] = useState(0)
  const [lastEvent, setLastEvent] = useState(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)

  const esRef = useRef(null)
  const retryDelayRef = useRef(INITIAL_RECONNECT_DELAY)
  const retryTimerRef = useRef(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!applicationId || !mountedRef.current) return
    if (esRef.current) {
      esRef.current.close()
    }

    const url = `${SSE_BASE}/${applicationId}/events`
    const es = new EventSource(url)
    esRef.current = es

    es.onopen = () => {
      if (!mountedRef.current) return
      setConnected(true)
      setError(null)
      retryDelayRef.current = INITIAL_RECONNECT_DELAY
    }

    // Handle named events
    ;['connected', 'update', 'status_changed', 'ocr_completed', 'payment_completed',
      'mismatch_detected', 'mismatch_resolved', 'submitted_for_verification',
      'approved', 'heartbeat'].forEach((evtName) => {
      es.addEventListener(evtName, (e) => {
        if (!mountedRef.current) return
        try {
          const data = JSON.parse(e.data)
          setLastEvent({ type: evtName, data, timestamp: new Date() })

          if (data.status) setStatus(data.status)
          if (data.progress !== undefined) setProgress(data.progress)
        } catch {}
      })
    })

    // Fallback message handler
    es.onmessage = (e) => {
      if (!mountedRef.current) return
      try {
        const data = JSON.parse(e.data)
        setLastEvent({ type: 'message', data, timestamp: new Date() })
      } catch {}
    }

    es.onerror = () => {
      if (!mountedRef.current) return
      setConnected(false)
      es.close()

      // Exponential backoff reconnect
      const delay = Math.min(retryDelayRef.current, MAX_RECONNECT_DELAY)
      retryDelayRef.current = delay * 1.5

      retryTimerRef.current = setTimeout(() => {
        if (mountedRef.current) connect()
      }, delay)
    }
  }, [applicationId])

  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }
      setConnected(false)
    }
  }, [connect])

  return { status, progress, lastEvent, connected, error }
}
