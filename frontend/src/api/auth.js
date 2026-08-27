import request from './request'

export function login(payload) {
  // 后端返回 { access_token, token_type, user_id, username, role }
  return request.post('/auth/login', payload)
}

export function register(payload) {
  return request.post('/auth/register', payload)
}

export function getMe() {
  return request.get('/users/me')
}

export function updateMe(payload) {
  return request.patch('/users/me', payload)
}
