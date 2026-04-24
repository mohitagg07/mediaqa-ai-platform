import { useState, useRef } from 'react'
import { Upload, CheckCircle, AlertCircle } from 'lucide-react'
import { uploadAPI } from '../services/api'
import toast from 'react-hot-toast'
import './UploadZone.css'

const ACCEPT = '.pdf,.mp3,.wav,.m4a,.ogg,.mp4,.mkv,.avi,.mov,.webm'

export default function UploadZone({ onUploaded }) {
  const [drag, setDrag]       = useState(false)
  const [state, setState]     = useState('idle')   // idle|uploading|ok|err
  const [progress, setProgress] = useState(0)
  const inputRef              = useRef(null)

  const process = async (file) => {
    if (!file) return
    setState('uploading')
    setProgress(0)
    try {
      const res = await uploadAPI.uploadFile(file, p => setProgress(p))
      setState('ok')
      toast.success(`"${file.name}" processed!`)
      onUploaded?.(res.data)
      setTimeout(() => setState('idle'), 2500)
    } catch (e) {
      setState('err')
      const msg = e.response?.data?.detail || 'Upload failed'
      toast.error(msg, { duration: 6000 })
      setTimeout(() => setState('idle'), 4000)
    } finally {
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const onDrop = (e) => {
    e.preventDefault(); setDrag(false)
    process(e.dataTransfer.files?.[0])
  }

  return (
    <div
      className={`uz ${drag ? 'drag' : ''} state-${state}`}
      onDragOver={e => { e.preventDefault(); setDrag(true) }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
      onClick={() => state === 'idle' && inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
    >
      <input
        ref={inputRef} type="file" accept={ACCEPT} hidden
        onChange={e => process(e.target.files?.[0])}
      />

      {state === 'uploading' && (
        <div className="uz-uploading">
          <div className="uz-prog"><div style={{ width: `${progress}%` }} /></div>
          <span>Uploading {progress}%</span>
        </div>
      )}

      {state === 'ok' && (
        <div className="uz-status ok">
          <CheckCircle size={14} /> Ready
        </div>
      )}

      {state === 'err' && (
        <div className="uz-status err">
          <AlertCircle size={14} /> Failed — check terminal
        </div>
      )}

      {state === 'idle' && (
        <div className="uz-idle">
          <Upload size={16} />
          <span>Upload file</span>
        </div>
      )}
    </div>
  )
}
