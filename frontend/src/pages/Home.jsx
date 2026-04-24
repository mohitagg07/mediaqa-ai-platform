import { useNavigate } from 'react-router-dom'
import { FileText, Music, Video, Clock, Brain, Zap, Upload, MessageSquare, Search } from 'lucide-react'
import './Home.css'

export default function Home() {
  const navigate = useNavigate()
  return (
    <div className="home">
      <nav className="home-nav">
        <span className="home-logo">media<span>QA</span></span>
        <div className="home-nav-right">
          <button className="btn btn-ghost" onClick={() => navigate('/auth')}>Sign in</button>
          <button className="btn btn-primary" onClick={() => navigate('/dashboard')}>Open App</button>
        </div>
      </nav>

      <section className="home-hero">
        <div className="home-pill">
          <Zap size={11} /> Powered by Groq LLM · Whisper ASR · FAISS Vector Search
        </div>
        <h1 className="home-h1">
          Ask questions about<br />
          <span className="home-gradient">any file you upload</span>
        </h1>
        <p className="home-desc">
          Upload PDFs, audio, or video. Get instant AI-powered answers with
          source citations and one-click timestamp navigation.
        </p>
        <div className="home-cta">
          <button className="btn btn-primary home-cta-btn" onClick={() => navigate('/dashboard')}>
            <Upload size={15} style={{ marginRight: 6 }} /> Upload a file
          </button>
        </div>

        <div className="home-features">
          {[
            { icon: <FileText size={14} />, text: 'PDF Analysis' },
            { icon: <Music size={14} />,    text: 'Audio Transcription' },
            { icon: <Video size={14} />,    text: 'Video Q&A' },
            { icon: <Clock size={14} />,    text: 'Timestamp Jump' },
            { icon: <Brain size={14} />,    text: 'Semantic Search' },
          ].map(f => (
            <div key={f.text} className="home-feat">
              <span>{f.icon}</span>{f.text}
            </div>
          ))}
        </div>
      </section>

      <section className="home-how">
        <h2 className="home-how-title">How it works</h2>
        <div className="home-steps">
          {[
            {
              icon: <Upload size={22} />,
              step: '01',
              title: 'Upload your file',
              desc: 'Drop a PDF, MP3, WAV, or MP4. We handle transcription and indexing automatically.',
            },
            {
              icon: <Search size={22} />,
              step: '02',
              title: 'AI processes it',
              desc: 'Whisper transcribes audio. FAISS indexes content. Chunks are ready for precise semantic retrieval.',
            },
            {
              icon: <MessageSquare size={22} />,
              step: '03',
              title: 'Ask anything',
              desc: 'Chat with your file. Get grounded answers with source citations and jump to exact timestamps.',
            },
          ].map(s => (
            <div key={s.step} className="home-step">
              <div className="home-step-icon">{s.icon}</div>
              <div className="home-step-num">{s.step}</div>
              <h3 className="home-step-title">{s.title}</h3>
              <p className="home-step-desc">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="home-footer">
        FastAPI · React · FAISS · Groq · MongoDB · Whisper
      </footer>
    </div>
  )
}
