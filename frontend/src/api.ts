import axios from 'axios'

export interface CurrentUser {
  id: string
  email: string
  is_subscriber: boolean
}

export interface DocumentRecord {
  id: string
  source_type: string
  source_value: string
  status: string
  created_at?: string
  updated_at?: string
  error_message?: string | null
}

const AUTH_STORAGE_KEY = 'auth_token'

const api = axios.create({
  baseURL: '/api',
})

let authToken = localStorage.getItem(AUTH_STORAGE_KEY)

api.interceptors.request.use((config) => {
  if (authToken && config.headers) {
    config.headers.Authorization = `Bearer ${authToken}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearAuthToken()
    }
    return Promise.reject(error)
  },
)

export const setAuthToken = (token: string | null) => {
  authToken = token
  if (token) {
    localStorage.setItem(AUTH_STORAGE_KEY, token)
    api.defaults.headers.common.Authorization = `Bearer ${token}`
  } else {
    clearAuthToken()
  }
}

export const clearAuthToken = () => {
  authToken = null
  localStorage.removeItem(AUTH_STORAGE_KEY)
  delete api.defaults.headers.common.Authorization
}

export const getStoredToken = () => authToken

export const uploadDocument = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export const submitUrl = (url: string) => {
  return api.post('/documents/from-url', { url })
}

export const getDocumentStatus = (documentId: string) => {
  return api.get(`/documents/${documentId}/status`)
}

export const listDocuments = () => {
  return api.get<DocumentRecord[]>('/documents')
}

export const qaQuery = (documentId: string, question: string, model: string = 'mini') => {
  return api.post('/qa/query', { document_id: documentId, question, model })
}

export const generateAnalysis = (documentId: string) => {
  return api.post('/qa/analysis/generate', { document_id: documentId })
}

export const getAnalysis = (documentId: string) => {
  return api.get(`/qa/analysis/${documentId}`)
}

export const fetchCurrentUser = () => {
  return api.get<CurrentUser>('/auth/me')
}

