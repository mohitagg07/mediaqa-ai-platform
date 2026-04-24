import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({ baseURL: BASE, timeout: 120000 })

api.interceptors.request.use(cfg => {
  const t = localStorage.getItem('token')
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})

export const authAPI = {
  login:    d => api.post('/auth/login', d),
  register: d => api.post('/auth/register', d),
}

export const uploadAPI = {
  uploadFile: (file, onProgress) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress
        ? e => onProgress(Math.round((e.loaded * 100) / e.total))
        : undefined,
    })
  },
  listFiles: ()       => api.get('/upload/files'),
  getFile:   (id)     => api.get(`/upload/files/${id}`),
}

export const chatAPI = {
  ask: (fileId, question) => api.post('/chat', { file_id: fileId, question }),
}

export const summaryAPI = {
  getSummary: (id) => api.get(`/summary/${id}`),
}

export default api
