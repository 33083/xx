import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import router from '@/router'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: 30000,
})

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
    const detail = error.response?.data?.detail
    if (status === 401) {
      const userStore = useUserStore()
      userStore.logout()
      ElMessage.error('登录已失效，请重新登录')
      router.push('/login')
    } else if (detail) {
      ElMessage.error(typeof detail === 'string' ? detail : '请求失败')
    } else {
      ElMessage.error('网络异常，请稍后重试')
    }
    return Promise.reject(error)
  },
)

export default request
