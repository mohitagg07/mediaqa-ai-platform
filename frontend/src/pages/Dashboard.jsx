import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FileText, Music, Video, ChevronRight, Layers,
  MessageSquare, LogOut, Home, Menu, X, Plus,
  Clock, Search
} from 'lucide-react'
import { uploadAPI } from '../services/api'
import UploadZone from '../components/UploadZone'
import ChatInterface from '../components/ChatInterface'
import MediaPlayer from '../components/MediaPlayer'
import Summary from '../components/Summary'
import toast from 'react-hot-toast'
import './Dashboard.css'

const TYPE_ICON  = { pdf: FileText, audio: Music, video: Video }
const TYPE_COLOR = { pdf: 'var(--purple)', audio: 'var(--green)', video: 'var(--amber)' }

export default function Dashboard() {
  const [files, setFiles]           = useState([])
  const [selected, setSelected]     = useState(null)
  const [tab, setTab]               = useState('chat')
  const [loading, setLoading]       = useState(true)
  const [sidebar, setSidebar]       = useState(true)
  const [search, setSearch]         = useState('')
  const playerRef                   = useRef(null)
  const navigate                    = useNavigate()
  const isAuth                      = !!localStorage.getItem('token')

  useEffect(() => { fetchFiles() }, [])

  const fetchFiles = async () => {
    try {
      const r = await uploadAPI.listFiles()
      setFiles(r.data.files || [])
    } catch { toast.error('Could not load files') }
    finally { setLoading(false) }
  }

  const handleUploaded = (data) => {
    setFiles(p => [data, ...p])
    setSelected(data)
    setTab('chat')
    toast.success('File ready — start asking!')
  }

  const handleSelect = async (f) => {
    if (f.file_id === selected?.file_id) return
    try {
      const r = await uploadAPI.getFile(f.file_id)
      setSelected(r.data)
      setTab('chat')
    } catch { toast.error('Could not load file') }
  }

  const seekTo = (s) => playerRef.current?.seekTo(s)

  const logout = () => {
    localStorage.removeItem('token')
    toast.success('Signed out')
    navigate('/')
  }

  const ftype    = selected?.type
  const TypeIcon = selected ? (TYPE_ICON[ftype] || FileText) : null
  const filtered = files.filter(f =>
    f.filename?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="db">
      {/* ─── SIDEBAR ─────────────────────────── */}
      <aside className={`db-sidebar ${sidebar ? '' : 'collapsed'}`}>
        <div className="db-sb-top">
          <div className="db-sb-brand">
            <span className="db-logo" onClick={() => navigate('/')}>
              media<span>QA</span>
            </span>
            <button className="btn-icon" onClick={() => setSidebar(false)}>
              <X size={15} />
            </button>
          </div>

          {/* Search */}
          <div className="db-sb-search">
            <Search size={13} className="db-sb-search-icon" />
            <input
              className="db-sb-search-input"
              placeholder="Search files…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          {/* Upload */}
          <UploadZone onUploaded={handleUploaded} />
        </div>

        {/* File list */}
        <div className="db-sb-files-header">
          <span className="db-sb-section-label">
            <Layers size={11} /> Files
          </span>
          <span className="db-sb-count">{files.length}</span>
        </div>

        <div className="db-sb-list">
          {loading ? (
            <div className="db-sb-loading"><span className="spin" /></div>
          ) : filtered.length === 0 ? (
            <div className="db-sb-empty">
              {search ? 'No matches' : 'No files yet'}
            </div>
          ) : filtered.map(f => {
            const Icon    = TYPE_ICON[f.type] || FileText
            const color   = TYPE_COLOR[f.type] || 'var(--text-2)'
            const isActive = selected?.file_id === f.file_id
            return (
              <button
                key={f.file_id}
                className={`db-sb-item ${isActive ? 'active' : ''}`}
                onClick={() => handleSelect(f)}
              >
                <span className="db-sb-item-icon" style={{ color }}>
                  <Icon size={13} />
                </span>
                <span className="db-sb-item-name" title={f.filename}>
                  {f.filename}
                </span>
                {isActive && <ChevronRight size={12} className="db-sb-item-arrow" />}
              </button>
            )
          })}
        </div>

        {/* Footer */}
        <div className="db-sb-footer">
          <button className="db-sb-footer-btn" onClick={() => navigate('/')}>
            <Home size={13} /> Home
          </button>
          {isAuth
            ? <button className="db-sb-footer-btn" onClick={logout}><LogOut size={13} /> Sign out</button>
            : <button className="db-sb-footer-btn" onClick={() => navigate('/auth')}><Plus size={13} /> Sign in</button>
          }
        </div>
      </aside>

      {/* ─── MAIN ────────────────────────────── */}
      <main className="db-main">
        {/* Topbar */}
        <header className="db-topbar">
          <div className="db-topbar-left">
            {!sidebar && (
              <button className="btn-icon" onClick={() => setSidebar(true)}>
                <Menu size={16} />
              </button>
            )}
            {selected ? (
              <div className="db-topbar-file">
                {TypeIcon && <TypeIcon size={15} style={{ color: TYPE_COLOR[ftype], flexShrink: 0 }} />}
                <span className="db-topbar-filename">{selected.filename}</span>
                <span className={`badge badge-${ftype}`}>{ftype?.toUpperCase()}</span>
                {selected.timestamps?.length > 0 && (
                  <span className="db-topbar-meta">
                    <Clock size={11} /> {selected.timestamps.length} segments
                  </span>
                )}
              </div>
            ) : (
              <span className="db-topbar-hint">← Select or upload a file</span>
            )}
          </div>
          <div className="db-topbar-right">
            {!isAuth && (
              <button className="btn btn-ghost" onClick={() => navigate('/auth')} style={{ fontSize: '0.8rem', padding: '6px 14px' }}>
                Sign in
              </button>
            )}
          </div>
        </header>

        {/* Workspace */}
        <div className="db-workspace">
          {!selected ? (
            <EmptyState />
          ) : (
            <div className="db-content fade-up">
              {/* Media player */}
              {(ftype === 'audio' || ftype === 'video') && (
                <div className="db-player-wrap">
                  <MediaPlayer
                    ref={playerRef}
                    src={`http://localhost:8000/static/${selected.file_id}.${selected.filename?.split('.').pop()}`}
                    fileType={ftype}
                  />
                </div>
              )}

              {/* Tab bar */}
              <div className="db-tabs">
                <button
                  className={`db-tab ${tab === 'chat' ? 'active' : ''}`}
                  onClick={() => setTab('chat')}
                >
                  <MessageSquare size={13} /> Chat
                </button>
                <button
                  className={`db-tab ${tab === 'summary' ? 'active' : ''}`}
                  onClick={() => setTab('summary')}
                >
                  <FileText size={13} /> Summary
                </button>
              </div>

              {/* Panel */}
              <div className="db-panel">
                {tab === 'chat'
                  ? <ChatInterface fileId={selected.file_id} fileType={ftype} onTimestamp={seekTo} />
                  : <Summary fileId={selected.file_id} initialSummary={selected.summary} />
                }
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="db-empty">
      <div className="db-empty-blob" />
      <div className="db-empty-card">
        <div className="db-empty-icon">
          <MessageSquare size={26} />
        </div>
        <h2>What's on your mind today?</h2>
        <p>Upload a PDF, audio, or video file from the sidebar to start asking questions with AI.</p>
        <div className="db-empty-types">
          {[
            { icon: <FileText size={13} />, label: 'PDF document',  color: 'var(--purple)' },
            { icon: <Music    size={13} />, label: 'Audio / Podcast', color: 'var(--green)' },
            { icon: <Video    size={13} />, label: 'Video file',    color: 'var(--amber)' },
          ].map(t => (
            <div key={t.label} className="db-empty-type" style={{ '--c': t.color }}>
              <span style={{ color: t.color }}>{t.icon}</span>
              {t.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
