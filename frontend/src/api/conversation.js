import request from './request'
import { useUserStore } from '@/stores/user'

export function createConversation(payload) {
  return request.post('/conversations', payload || {})
}

export function listConversations() {
  return request.get('/conversations')
}

export function deleteConversation(cid) {
  return request.delete(`/conversations/${cid}`)
}

export function updateConversationTitle(cid, title) {
  return request.patch(`/conversations/${cid}/title`, { title })
}

export function searchConversations(q) {
  return request.get('/conversations/search', { params: { q } })
}

export function listMessages(cid) {
  return request.get(`/conversations/${cid}/messages`)
}

export function chatSync(payload) {
  return request.post('/conversations/chat', payload)
}

/**
 * SSE 流式聊天。
 * onEvent 会被回调 { event, payload }：
 *  - start:    { conversation_id, refs }
 *  - delta:    { content }
 *  - end:      { conversation_id, message_id, chars }
 *  - error:    { detail }
 * @returns {Promise<{stop: function}>} 可手动中止
 */
export function chatStream(payload, onEvent) {
  const ctrl = new AbortController()
  const promise = new Promise((resolve, reject) => {
    const userStore = useUserStore()
    if (!userStore.token) {
      reject(new Error('未登录'))
      return
    }
    const base = import.meta.env.VITE_API_BASE || '/api/v1'
    const url = base + '/conversations/chat/stream'
    let es = null
    try {
      const u = new URL(url, window.location.origin)
      const body = JSON.stringify(payload)
      fetch(u.toString(), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + userStore.token,
          'Accept': 'text/event-stream',
        },
        body,
        signal: ctrl.signal,
      }).then(async (resp) => {
        if (!resp.ok) {
          const txt = await resp.text().catch(() => '')
          let detail = `HTTP ${resp.status}`
          try {
            const j = JSON.parse(txt)
            if (j.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
          } catch (_) {}
          onEvent && onEvent({ event: 'error', payload: { detail } })
          reject(new Error(detail))
          return
        }
        const reader = resp.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let buf = ''
        let currentEvent = 'message'
        while (true) {
          const { value, done } = await reader.read()
          if (value) buf += decoder.decode(value, { stream: true })
          // 按空行切成帧
          while (true) {
            const sepIdx = buf.indexOf('\n\n')
            if (sepIdx === -1) break
            const frame = buf.slice(0, sepIdx)
            buf = buf.slice(sepIdx + 2)
            let dataLines = ''
            for (const line of frame.split('\n')) {
              if (line.startsWith('event:')) {
                currentEvent = line.slice(6).trim()
              } else if (line.startsWith('data:')) {
                dataLines += line.slice(5).trimStart() + '\n'
              }
            }
            const dataStr = dataLines.replace(/\n$/, '')
            if (!dataStr) continue
            let payload = dataStr
            try {
              payload = JSON.parse(dataStr)
            } catch (_) {}
            onEvent && onEvent({ event: currentEvent, payload })
            currentEvent = 'message'
            if (done) break
          }
          if (done) break
        }
        resolve({ stop: () => {} })
      }).catch((e) => {
        if (e && e.name === 'AbortError') {
          // 用户手动停止：正常结束，不发错误事件
          onEvent && onEvent({ event: 'end', payload: { aborted: true } })
          resolve({ stop: () => {} })
          return
        }
        onEvent && onEvent({ event: 'error', payload: { detail: e.message || String(e) } })
        reject(e)
      })
    } catch (e) {
      onEvent && onEvent({ event: 'error', payload: { detail: e.message || String(e) } })
      reject(e)
    }
  })
  return { promise, abort: () => ctrl.abort() }
}
