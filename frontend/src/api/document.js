import request from './request'

export function uploadDocument(file, { category, description } = {}) {
  const form = new FormData()
  form.append('file', file)
  if (category) form.append('category', category)
  if (description) form.append('description', description)
  return request.post('/documents/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000,
  })
}

export function listDocuments(params = {}) {
  return request.get('/documents', { params })
}

export function deleteDocument(id) {
  return request.delete(`/documents/${id}`)
}

export function searchDocuments(q, top_k = 4) {
  return request.get('/documents/search', { params: { q, top_k } })
}

export function updateDocument(id, payload) {
  return request.patch(`/documents/${id}`, payload)
}

export function previewDocument(id) {
  return request.get(`/documents/${id}/preview`)
}

export function getFileBlob(id) {
  return request.get(`/documents/${id}/file`, { responseType: 'blob' })
}
