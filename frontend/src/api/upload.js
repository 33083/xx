import request from './request'

/**
 * 上传图片（多模态用）。
 * 注意：request.js 拦截器已经把后端 ApiResponse 的 data 解开返回，
 * 所以这里直接返回 response（即 {url, filename, size}），不要再 .data。
 * @param {File} file 浏览器 File 对象
 * @returns {Promise<{url: string, filename: string, size: number}>}
 */
export function uploadImage(file) {
  const form = new FormData()
  form.append('file', file)
  return request.post('/uploads/image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
