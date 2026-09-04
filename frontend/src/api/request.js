import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import router from '@/router'

/**
 * 统一 HTTP 请求封装
 * - 默认超时 30s；预览/下载大文件等耗时接口在单独调用处传 { timeout: 120_000 } 覆盖
 * - 错误提示更具体：区分超时、断连、CORS、后端返回 detail
 */
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: 30000,
})

/** 把 axios 错误翻译成用户能看懂的中文 */
function _friendlyError(error) {
  // 后端明确返回了错误信息
  if (error.response) {
    const status = error.response.status
    const detail = error.response.data?.detail
    const msg = error.response.data?.msg
    if (detail) return typeof detail === 'string' ? detail : '请求失败'
    if (msg) return msg
    if (status === 400) return '参数有误，请检查后重试'
    if (status === 401) return '登录已失效，请重新登录'
    if (status === 403) return '没有权限执行此操作'
    if (status === 404) return '资源不存在'
    if (status === 429) return '操作过于频繁，稍后再试'
    if (status === 413) return '文件过大，超出上传限制'
    if (status >= 500) return `服务器异常 (${status})，请稍后重试`
    return `请求失败 (HTTP ${status})`
  }
  // 断连/超时/跨域等 axios 层错误（没有 response）
  if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
    const s = Math.round((error.config?.timeout || 30000) / 1000)
    return `请求超时（${s}秒）：文件过大或服务器繁忙，稍后重试`
  }
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return '网络已断开，请检查连接后重试'
  }
  if (error.message?.includes('Network Error') || error.code === 'ERR_NETWORK') {
    // "Network Error"（axios 1.x）/ "ERR_NETWORK"（axios 1.6+）在浏览器里常见于：
    //  ① Vite dev 代理转发到的后端 127.0.0.1:8000 没启动
    //  ② Vite 的 http-proxy ECONNRESET（后端长传输中途断开，比如大 PDF）
    //  ③ CORS 预检被拦
    // 把实际请求的 URL 展示给用户方便排查：优先请求 URL，其次 baseURL，再 window.origin
    const cfg = error.config || {}
    const urlGuess = cfg.url
      ? (cfg.baseURL ? (cfg.baseURL + cfg.url).replace(/(https?:\/\/[^\/]+)(?=\/api\/v\d|\/docs)/, '') : cfg.url)
      : (cfg.baseURL || (typeof window !== 'undefined' ? (window.location.origin + '/api/v1') : '/api/v1'))
    const proxyTarget = 'http://127.0.0.1:8000'
    return `后端接口无法连接（${urlGuess}）：Vite 代理转发到 ${proxyTarget} 失败，` +
      `请确认后端是否已启动（一键启动.bat 或 uvicorn :8000），或稍后重试`
  }
  if (error.message?.includes('CORS') || error.message?.includes('blocked')) {
    return '跨域被阻止，请确认后端服务已启动'
  }
  return `网络异常：${error.message || '请稍后重试'}`
}

// 请求拦截：自动带 token
request.interceptors.request.use(
  (config) => {
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (err) => Promise.reject(err),
)

// 响应拦截：统一处理错误
request.interceptors.response.use(
  (response) => {
    const data = response.data
    // blob 类响应直接原路返回（PDF 预览/下载文件）
    if (response.config.responseType === 'blob') {
      const ct = response.headers['content-type'] || ''
      // blob 也可能是后端返回的 { code, msg } JSON 错误
      if (ct.includes('application/json')) {
        return new Promise((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => {
            try {
              const json = JSON.parse(reader.result)
              if (json && json.code !== 0) {
                // 重要：抛错时要带原 response.config，
                // 这样进入 error 拦截器时 !error.config?._silent 才会生效
                const err = new Error(json.msg || '请求失败')
                err.config = response.config
                reject(err)
              } else {
                resolve(response.data)
              }
            } catch {
              resolve(response.data)
            }
          }
          reader.readAsText(response.data)
        })
      }
      return data
    }
    // 后端 ApiResponse 格式：{ code, msg, data }
    if (data && typeof data === 'object' && 'code' in data) {
      if (data.code !== 0) {
        ElMessage.error(data.msg || '请求失败')
        return Promise.reject(new Error(data.msg || '请求失败'))
      }
      return data.data
    }
    // 非 ApiResponse 结构（如 Token），原样返回
    return data
  },
  (error) => {
    const status = error.response?.status
    if (status === 401) {
      const userStore = useUserStore()
      userStore.logout()
      ElMessage.error('登录已失效，请重新登录')
      router.push('/login')
    } else {
      const msg = _friendlyError(error)
      if (!error.config?._silent) {
        ElMessage.error(msg)
      }
      error.friendlyMsg = msg
    }
    return Promise.reject(error)
  },
)

export default request
