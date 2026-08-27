import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authApi from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref(sessionStorage.getItem('token') || '')
  const username = ref(sessionStorage.getItem('username') || '')
  const role = ref(sessionStorage.getItem('role') || 'student')
  const profile = ref(null)

  const isLogin = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin')

  function setAuth(data) {
    token.value = data.access_token
    username.value = data.username
    role.value = data.role
    sessionStorage.setItem('token', data.access_token)
    sessionStorage.setItem('username', data.username)
    sessionStorage.setItem('role', data.role)
  }

  function logout() {
    token.value = ''
    username.value = ''
    role.value = 'student'
    profile.value = null
    sessionStorage.removeItem('token')
    sessionStorage.removeItem('username')
    sessionStorage.removeItem('role')
  }

  async function fetchMe() {
    const data = await authApi.getMe()
    profile.value = data
    return data
  }

  return {
    token,
    username,
    role,
    profile,
    isLogin,
    isAdmin,
    setAuth,
    logout,
    fetchMe,
  }
})
