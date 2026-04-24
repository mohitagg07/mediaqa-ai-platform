import { useRef, useState, useEffect, forwardRef, useImperativeHandle } from 'react'
import { Play, Pause, Volume2, VolumeX, Maximize2 } from 'lucide-react'
import './MediaPlayer.css'

const MediaPlayer = forwardRef(function MediaPlayer({ src, fileType }, ref) {
  const elRef        = useRef(null)
  const progressRef  = useRef(null)
  const [playing, setPlaying]   = useState(false)
  const [muted,   setMuted]     = useState(false)
  const [current, setCurrent]   = useState(0)
  const [dur,     setDur]       = useState(0)
  const [vol,     setVol]       = useState(1)
  const [jumped,  setJumped]    = useState(null)   // {time, label} shown as toast

  /* Expose seekTo to parent */
  useImperativeHandle(ref, () => ({
    seekTo(sec) {
      const el = elRef.current
      if (!el) return
      el.currentTime = sec
      el.play().catch(() => {})
      setPlaying(true)
      setJumped(fmt(sec))
      setTimeout(() => setJumped(null), 2800)
    }
  }))

  useEffect(() => {
    const el = elRef.current; if (!el) return
    const onTime = () => setCurrent(el.currentTime)
    const onMeta = () => setDur(el.duration || 0)
    const onEnd  = () => setPlaying(false)
    el.addEventListener('timeupdate',    onTime)
    el.addEventListener('loadedmetadata', onMeta)
    el.addEventListener('ended',          onEnd)
    return () => {
      el.removeEventListener('timeupdate',    onTime)
      el.removeEventListener('loadedmetadata', onMeta)
      el.removeEventListener('ended',          onEnd)
    }
  }, [src])

  const toggle = () => {
    const el = elRef.current; if (!el) return
    if (playing) { el.pause(); setPlaying(false) }
    else         { el.play().catch(() => {}); setPlaying(true) }
  }

  const toggleMute = () => {
    if (elRef.current) { elRef.current.muted = !muted; setMuted(!muted) }
  }

  const seek = (e) => {
    if (!progressRef.current || !dur) return
    const r = progressRef.current.getBoundingClientRect()
    const p = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width))
    if (elRef.current) elRef.current.currentTime = p * dur
  }

  const changeVol = (e) => {
    const v = parseFloat(e.target.value)
    setVol(v); setMuted(v === 0)
    if (elRef.current) elRef.current.volume = v
  }

  const fmt = (s) => {
    if (!s || isNaN(s)) return '0:00'
    const m = Math.floor(s / 60), sc = Math.floor(s % 60)
    return `${m}:${sc.toString().padStart(2, '0')}`
  }

  const pct = dur ? (current / dur) * 100 : 0

  return (
    <div className="mp">
      {jumped && (
        <div className="mp-toast">▶ Jumped to {jumped}</div>
      )}

      {fileType === 'video' ? (
        <video
          ref={elRef} src={src}
          className="mp-video"
          onClick={toggle}
          preload="metadata"
          onError={e => console.error('Video load error:', e)}
        />
      ) : (
        <div className="mp-audio-vis">
          {Array.from({ length: 28 }).map((_, i) => (
            <div
              key={i}
              className={`mp-bar ${playing ? 'active' : ''}`}
              style={{
                height: `${14 + Math.abs(Math.sin(i * 1.1)) * 18}px`,
                animationDelay: `${i * 0.055}s`
              }}
            />
          ))}
          <audio ref={elRef} src={src} preload="metadata" onError={e => console.error('Audio error:', e)} />
        </div>
      )}

      <div className="mp-ctrl">
        {/* Progress bar */}
        <div className="mp-prog-wrap" ref={progressRef} onClick={seek}>
          <div className="mp-prog-bg">
            <div className="mp-prog-fill" style={{ width: `${pct}%` }} />
            <div className="mp-prog-thumb" style={{ left: `${pct}%` }} />
          </div>
        </div>

        <div className="mp-row">
          <div className="mp-left">
            <button className="mp-btn" onClick={toggle} aria-label={playing ? 'Pause' : 'Play'}>
              {playing ? <Pause size={14} /> : <Play size={14} />}
            </button>
            <button className="mp-btn" onClick={toggleMute} aria-label="Toggle mute">
              {muted || vol === 0 ? <VolumeX size={13} /> : <Volume2 size={13} />}
            </button>
            <input
              type="range" className="mp-vol"
              min={0} max={1} step={0.05}
              value={muted ? 0 : vol}
              onChange={changeVol}
              aria-label="Volume"
            />
          </div>

          <span className="mp-time mono">{fmt(current)} / {fmt(dur)}</span>

          {fileType === 'video' && (
            <button className="mp-btn" onClick={() => elRef.current?.requestFullscreen()} aria-label="Fullscreen">
              <Maximize2 size={12} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
})

export default MediaPlayer
