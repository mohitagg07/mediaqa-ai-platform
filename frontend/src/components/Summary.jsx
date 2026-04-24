import { useState, useEffect } from 'react'
import { summaryAPI } from '../services/api'
import { RefreshCw, FileText, AlertCircle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import toast from 'react-hot-toast'
import './Summary.css'

export default function Summary({ fileId, initialSummary }) {
  const [summary, setSummary] = useState(initialSummary || null)
  const [loading, setLoading] = useState(!initialSummary)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    setSummary(initialSummary || null)
    setError(null)
    if (!initialSummary) fetchSummary()
  }, [fileId])

  const fetchSummary = async () => {
    setLoading(true); setError(null)
    try {
      const r = await summaryAPI.getSummary(fileId)
      setSummary(r.data.summary)
    } catch (e) {
      const msg = e.response?.data?.detail || 'Could not load summary'
      setError(msg)
      toast.error(msg)
    } finally { setLoading(false) }
  }

  return (
    <div className="sm">
      <div className="sm-header">
        <div className="sm-header-left">
          <FileText size={14} style={{ color: 'var(--accent)' }} />
          <span>AI Summary</span>
        </div>
        <button className="sm-refresh" onClick={fetchSummary} disabled={loading} title="Regenerate summary">
          <RefreshCw size={13} className={loading ? 'spin' : ''} />
        </button>
      </div>

      <div className="sm-body">
        {loading ? (
          <div className="sm-loading">
            <span className="spin" style={{ width: 18, height: 18 }} />
            <span>Generating summary…</span>
          </div>
        ) : error ? (
          <div className="sm-error">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        ) : summary ? (
          <div className="sm-content">
            <ReactMarkdown
              components={{
                h2: ({ children }) => <h2 className="sm-h2">{children}</h2>,
                h3: ({ children }) => <h3 className="sm-h3">{children}</h3>,
                ul: ({ children }) => <ul className="sm-ul">{children}</ul>,
                li: ({ children }) => <li className="sm-li">{children}</li>,
                p:  ({ children }) => <p  className="sm-p">{children}</p>,
                strong: ({ children }) => <strong className="sm-strong">{children}</strong>,
              }}
            >
              {summary}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="sm-empty">No summary available.</div>
        )}
      </div>
    </div>
  )
}
