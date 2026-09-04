import request from './request'

/**
 * 文档库接口
 * 上传/预览/下载大文件时，单独传更长的 timeout（大文档解析需要时间）
 */
export function uploadDocument(file, { category, description } = {}) {
  const form = new FormData()
  form.append('file', file)
  if (category) form.append('category', category)
  if (description) form.append('description', description)
  return request.post('/documents/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300_000, // 5 分钟：上传 + Word/PDF 解析 + 向量入库
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

/**
 * 预览元信息：返回 { file_type, preview_url?, text? }
 * 大文档 Word 提取文字可能比较慢 → 120s 超时
 */
export function previewDocument(id) {
  return request.get(`/documents/${id}/preview`, {
    timeout: 120_000,
  })
}

/**
 * 把文档文件下载为 Blob（PDF 预览用）
 * 大 PDF 可能要下载几十秒 → 180s 超时
 */
export function getFileBlob(id) {
  return request.get(`/documents/${id}/file`, {
    responseType: 'blob',
    timeout: 180_000,
  })
}
