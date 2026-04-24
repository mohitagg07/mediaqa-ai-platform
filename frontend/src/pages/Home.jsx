import { useNavigate } from 'react-router-dom'
import { FileText, Music, Video, Clock, Brain, Zap } from 'lucide-react'
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
          <Zap size={11} /> RAG powered by Groq and Whisper
        </div>
        <h1 className="home-h1">
          Ask questions about<br />
          <span className="home-gradient">any file you upload</span>
        </h1>
        <p className="home-desc">
          Upload a PDF, audio, or video. Get accurate AI answers with source references
          and instant timestamp navigation.
        </p>
        <div className="home-cta">
          <button className="btn btn-primary home-cta-btn" onClick={() => navigate('/dashboard')}>
            Upload a file
          </button>
          <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" className="btn btn-ghost home-cta-btn">
            API Docs
          </a>
        </div>

        <div className="home-features">
          {[
            { icon: <FileText size={14} />, text: 'PDF Analysis' },
            { icon: <Music size={14} />,    text: 'Audio Q&A' },
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

      <footer className="home-footer">
        FastAPI · React · FAISS · Groq · MongoDB · Whisper
      </footer>
    </div>
  )
}
