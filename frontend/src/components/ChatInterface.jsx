import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Send, Bot, User, Clock, ChevronRight,
  Zap, RotateCcw, BookOpen, ArrowRight
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { chatAPI } from '../services/api'
import toast from 'react-hot-toast'
import './ChatInterface.css'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const CHIPS = [
  'Summarize this file',
  'What are the key points?',
  'Explain the main topic',
  'List important details',
]

export default function ChatInterface({ fileId, fileType, onTimestamp }) {
  const [msgs, setMsgs]       = useState([])
  const [input, setInput]     = useState('')
  const [busy, setBusy]       = useState(false)
  const [stream, setStream]   = useState(true)
  const bottomRef             = useRef(null)
  const inputRef              = useRef(null)
  const abortRef              = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs])

  useEffect(() => {
    setMsgs([])
    setTimeout(() => inputRef.current?.focus(), 50)
    return () => abortRef.current?.abort()
  }, [fileId])

  /* ── Streaming ──────────────────────────── */
  const sendStream = useCallback(async (q) => {
    const aid = Date.now() + 1
    setMsgs(m => [...m, {
      id: aid, role: 'assistant', content: '',
      streaming: true, timestamp: null, timestamp_text: null, sources: []
    }])
    abortRef.current = new AbortController()
    try {
      const token = localStorage.getItem('token')
      const resp  = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ file_id: fileId, question: q }),
        signal: abortRef.current.signal,
      })
      if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail || `HTTP ${resp.status}`) }

      const reader  = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n'); buf = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const p = line.slice(6)
          if (p === '[DONE]') {
            setMsgs(m => m.map(x => x.id === aid ? { ...x, streaming: false } : x))
          } else if (p.startsWith('[META]')) {
            const meta = JSON.parse(p.slice(6))
            setMsgs(m => m.map(x => x.id === aid ? { ...x, ...meta } : x))
          } else if (p.startsWith('[ERROR]')) {
            toast.error(p.slice(7))
            setMsgs(m => m.map(x => x.id === aid ? { ...x, content: p.slice(7), streaming: false, role: 'error' } : x))
          } else {
            const tok = p.replace(/\\n/g, '\n')
            setMsgs(m => m.map(x => x.id === aid ? { ...x, content: x.content + tok } : x))
          }
        }
      }
    } catch (e) {
      if (e.name === 'AbortError') return
      toast.error(e.message || 'Streaming failed')
      setMsgs(m => m.map(x => x.id === aid ? { ...x, streaming: false } : x))
    } finally { setBusy(false) }
  }, [fileId])

  /* ── Blocking ───────────────────────────── */
  const sendBlock = useCallback(async (q) => {
    try {
      const r = await chatAPI.ask(fileId, q)
      const { answer, timestamp, timestamp_text, sources } = r.data
      setMsgs(m => [...m, { id: Date.now() + 1, role: 'assistant', content: answer, timestamp, timestamp_text, sources }])
    } catch (e) {
      const msg = e.response?.data?.detail || 'Something went wrong'
      toast.error(msg)
      setMsgs(m => [...m, { id: Date.now() + 1, role: 'error', content: msg }])
    } finally { setBusy(false) }
  }, [fileId])

  const send = async (q = input) => {
    const text = q.trim()
    if (!text || busy) return
    setMsgs(m => [...m, { id: Date.now(), role: 'user', content: text }])
    setInput('')
    setBusy(true)
    stream ? await sendStream(text) : await sendBlock(text)
  }

  const fmt = (s) => {
    if (s == null) return '0:00'
    const m = Math.floor(s / 60), sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  return (
    <div className="ci">
      {/* Toolbar */}
      <div className="ci-bar">
        <button
          className={`ci-toggle ${stream ? 'on' : ''}`}
          onClick={() => setStream(v => !v)}
          title="Toggle streaming"
        >
          <Zap size={11} /> {stream ? 'Streaming' : 'Buffered'}
        </button>
        {msgs.length > 0 && (
          <button className="ci-toggle" onClick={() => setMsgs([])} title="Clear">
            <RotateCcw size={11} /> Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="ci-msgs">
        {msgs.length === 0 ? (
          <div className="ci-empty">
            <div className="ci-empty-bot"><Bot size={24} /></div>
            <p className="ci-empty-h">Ask anything about this file</p>
            <p className="ci-empty-s">I'll use semantic search to find the exact answer from your content.</p>
            <div className="ci-chips">
              {CHIPS.map(c => (
                <button key={c} className="ci-chip" onClick={() => send(c)}>
                  <ArrowRight size={11} /> {c}
                </button>
              ))}
            </div>
          </div>
        ) : msgs.map(msg => (
          <div key={msg.id} className={`ci-row ${msg.role}`}>
            <div className="ci-avatar">
              {msg.role === 'user' ? <User size={12} /> : <Bot size={12} />}
            </div>
            <div className="ci-body">
              {/* Bubble */}
              {msg.role === 'user' ? (
                <div className="ci-bubble user">{msg.content}</div>
              ) : (
                <div className={`ci-bubble assistant ${msg.role === 'error' ? 'error' : ''}`}>
                  <div className="ci-md">
                    <ReactMarkdown>{msg.content || (msg.streaming ? '' : '…')}</ReactMarkdown>
                    {msg.streaming && <span className="ci-cursor">▍</span>}
                  </div>
                </div>
              )}

              {/* Timestamp jump */}
              {msg.timestamp != null && !msg.streaming && fileType !== 'pdf' && (
                <button className="ci-ts" onClick={() => onTimestamp?.(msg.timestamp)}>
                  <Clock size={12} />
                  <span>▶ Jump to {fmt(msg.timestamp)}</span>
                  {msg.timestamp_text && (
                    <span className="ci-ts-preview">"{msg.timestamp_text.slice(0, 50)}…"</span>
                  )}
                </button>
              )}

              {/* Sources */}
              {!msg.streaming && msg.sources?.length > 0 && (
                <div className="ci-sources">
                  <div className="ci-src-label">
                    <BookOpen size={11} />
                    {msg.sources.length} source chunk{msg.sources.length > 1 ? 's' : ''} used
                  </div>
                  <div className="ci-src-list">
                    {msg.sources.map((s, i) => (
                      <div key={i} className="ci-src-item">
                        <span className="ci-src-idx mono">{i + 1}</span>
                        <span className="ci-src-text">{s}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Thinking indicator */}
        {busy && !stream && (
          <div className="ci-row assistant">
            <div className="ci-avatar"><Bot size={12} /></div>
            <div className="ci-body">
              <div className="ci-bubble assistant">
                <div className="ci-thinking">
                  <span /><span /><span />
                  <span className="ci-thinking-label">Thinking…</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input row */}
      <div className="ci-input">
        <div className="ci-input-wrap">
          <textarea
            ref={inputRef}
            className="ci-textarea"
            placeholder="Ask a question about your file…"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            rows={1}
            disabled={busy}
          />
          <button
            className="ci-send"
            onClick={() => send()}
            disabled={!input.trim() || busy}
            title="Send"
          >
            {busy
              ? <span className="spin" style={{ width: 14, height: 14 }} />
              : <Send size={14} />
            }
          </button>
        </div>
        <p className="ci-hint">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  )
}
