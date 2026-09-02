<template>
  <div class="chat-page">
    <!-- 移动端：会话列表开关 + 遮罩 -->
    <div v-if="showSideMobile" class="side-mask" @click="showSideMobile = false"></div>
    <button class="mobile-menu-btn glass" title="会话列表" @click="showSideMobile = !showSideMobile">
      <el-icon :size="18"><ChatDotRound /></el-icon>
    </button>

    <!-- 左侧会话列表（玻璃面板） -->
    <aside class="side" :class="{ 'mobile-open': showSideMobile }">
      <div class="side-head">
        <span class="side-title">💬 会话列表</span>
        <div class="side-actions">
          <el-button
            class="head-ico"
            :icon="Download"
            size="small"
            circle
            title="导出当前会话"
            :disabled="!currentId"
            @click="exportConversation"
          />
          <el-button type="primary" size="small" :icon="Plus" @click="newConversation">新建</el-button>
        </div>
      </div>
      <div class="side-search">
        <el-input
          v-model="searchQ"
          size="small"
          placeholder="搜索会话 / 消息"
          :prefix-icon="Search"
          clearable
          @input="onSearchInput"
          @clear="clearSearch"
        />
      </div>
      <div class="side-list">
        <!-- 搜索结果 -->
        <template v-if="searching">
          <div
            v-for="(h, i) in searchResults"
            :key="i"
            class="search-item"
            @click="openSearchHit(h)"
          >
            <div class="search-type">{{ h.type === 'conversation' ? '会话' : '消息' }}</div>
            <div class="search-body">
              <div class="search-title">{{ h.title }}</div>
              <div class="search-snippet">{{ h.snippet }}</div>
            </div>
          </div>
          <el-empty v-if="!searchResults.length" description="无匹配结果" :image-size="60" />
        </template>
        <!-- 正常列表 -->
        <template v-else>
          <el-empty v-if="!conversations.length" description="暂无会话" :image-size="60" />
          <div
            v-for="c in conversations"
            :key="c.id"
            class="conv-item"
            :class="{ active: c.id === currentId }"
            @click="selectConv(c)"
            @dblclick="renameConv(c)"
          >
            <div class="conv-main">
              <div class="conv-title" :title="'双击可重命名'">{{ c.title }}</div>
              <div class="conv-meta">{{ c.agent_type }} · {{ c.message_count || 0 }} 条</div>
            </div>
            <el-button
              class="conv-del"
              type="danger"
              :icon="Delete"
              size="small"
              circle
              title="删除会话"
              @click.stop="removeConversation(c)"
            />
          </div>
        </template>
      </div>
    </aside>

    <!-- 右侧主区：消息列表 + 输入区 -->
    <section class="main">
      <!-- 消息列表 -->
      <div class="msg-list" ref="msgListRef">
        <!-- 空态：欢迎 + 建议 -->
        <div v-if="!messages.length" class="welcome">
          <div class="welcome-logo">
            <el-icon :size="30"><Promotion /></el-icon>
          </div>
          <div class="welcome-title grad-text">你好，我是你的学习求职助手</div>
          <div class="welcome-sub">知识库 RAG 检索 · 多模态图片理解 · 联网搜索 · 技能市场</div>
          <div class="suggests">
            <div v-for="s in suggestions" :key="s" class="suggest" @click="pickSuggestion(s)">
              {{ s }}
            </div>
          </div>
        </div>

        <div v-for="m in messages" :key="m._key || m.id" class="msg" :class="m.role">
          <!-- 助手消息 -->
          <template v-if="m.role === 'assistant'">
            <div class="avatar ai"><el-icon :size="18"><Promotion /></el-icon></div>
            <div class="bubble-wrap">
              <div class="bubble" :class="{ 'is-thinking': m._key === streaming && !m.content }">
                <template v-if="m._key === streaming && !m.content">
                  <span class="dot"></span><span class="dot"></span><span class="dot"></span>
                </template>
                <template v-else>
                  <MarkdownContent v-if="m.content" :content="m.content" />
                  <span v-if="m._key === streaming" class="cursor"></span>
                </template>
              </div>
              <!-- 追问推荐 -->
              <div v-if="m._followUps && m._followUps.length" class="follow-ups">
                <span class="fu-label">💡 可以继续问：</span>
                <span
                  v-for="(f, i) in m._followUps"
                  :key="i"
                  class="fu-chip"
                  :disabled="sending"
                  @click="askFollowUp(f)"
                >{{ f }}</span>
              </div>
              <div v-if="m._ragNotice" class="rag-notice">{{ m._ragNotice }}</div>
              <div v-if="m.tools && m.tools.length" class="tool-chips">
                <div
                  v-for="(t, ti) in m.tools"
                  :key="ti"
                  class="tool-chip"
                  :class="{ running: t.status === 'start' }"
                >
                  <span class="tool-icon">🔧</span>
                  <span class="tool-name">{{ t.name }}</span>
                  <span v-if="t.status === 'start'" class="tool-state">调用中…</span>
                  <span v-else class="tool-state ok">✓</span>
                </div>
              </div>
              <div v-if="m.refs && m.refs.length" class="refs">
                <div class="refs-title">
                  📎 参考资料<template v-if="hasDownloadable(m.refs)">（点击可下载原文）</template>
                </div>
                <div
                  v-for="(r, i) in m.refs"
                  :key="i"
                  class="ref-item"
                  :class="{ 'ref-clickable': isDownloadable(r) }"
                  :title="isDownloadable(r) ? '点击下载原文' : r.doc_title"
                  @click="isDownloadable(r) && downloadRef(r)"
                >
                  <span class="ref-idx">{{ i + 1 }}</span>
                  <span class="ref-doc">{{ r.doc_title || '(未知文档)' }}</span>
                  <span class="ref-src">{{ r.source === 'shared' ? '公共库' : '我的' }}</span>
                  <span class="ref-score">{{ (r.score || 0).toFixed(3) }}</span>
                </div>
              </div>
              <div class="msg-actions">
                <el-button size="small" text :icon="CopyDocument" @click="copyText(m.content)">复制</el-button>
                <el-button v-if="m.content" size="small" text :icon="Microphone" @click="speak(m.content)">朗读</el-button>
              </div>
            </div>
          </template>

          <!-- 用户消息 -->
          <template v-else>
            <div class="bubble-wrap">
              <div v-if="m.image_url" class="msg-image">
                <img :src="m.image_url" alt="用户上传图片" @click="previewImage(m.image_url)" />
              </div>
              <div class="bubble">{{ m.content }}</div>
              <div class="msg-actions">
                <el-button size="small" text :icon="CopyDocument" @click="copyText(m.content)">复制</el-button>
              </div>
            </div>
            <div class="avatar user"><el-icon :size="18"><UserFilled /></el-icon></div>
          </template>
        </div>
      </div>

      <!-- 输入区：固定底部 -->
      <div class="composer">
        <div v-if="pendingImage.url" class="pending-preview">
          <img :src="pendingImage.url" alt="待发送图片" />
          <div class="pending-meta">
            <div class="pending-name">{{ pendingImage.name }}</div>
            <div class="pending-size">{{ pendingImage.sizeText }}</div>
          </div>
          <el-button
            type="danger"
            size="small"
            :icon="Close"
            circle
            @click="clearPendingImage"
            :disabled="sending"
          />
        </div>

        <div class="input-row">
          <el-upload
            :show-file-list="false"
            :before-upload="handlePickImage"
            accept="image/png,image/jpeg,image/gif,image/webp,image/bmp"
            :disabled="sending"
          >
            <el-button class="ico-btn" :icon="Picture" :disabled="sending" title="上传图片（多模态）" />
          </el-upload>

          <!-- 输入框：左上角内置「文档 / 联网」，点击“文档”二字展开分类 -->
          <div class="input-box">
            <div class="input-toolbar">
              <span class="mode-chip" :class="{ on: docMode }" @click="toggleDocMode">📄 文档</span>
              <span class="mode-chip" :class="{ on: webSearch }" @click="toggleWebSearch">🌐 联网</span>
              <span
                v-if="ragCategory === 'interview'"
                class="mode-chip grill-chip"
                :class="{ on: grillMode }"
                @click="toggleGrillMode"
              >🎯 面试拷问</span>
            </div>
            <div v-if="docMode" class="cat-menu">
              <span
                v-for="opt in catOptions"
                :key="opt.value"
                class="cat-opt"
                :class="{ active: ragCategory === opt.value }"
                @click="ragCategory = opt.value; onCategoryChange()"
              >{{ opt.label }}</span>
            </div>
            <el-input
              v-model="input"
              type="textarea"
              :rows="2"
              resize="none"
              :disabled="sending"
              class="chat-input"
              placeholder="输入问题，Enter 发送，Shift+Enter 换行"
              @keydown.enter.exact.prevent="send"
            />
          </div>

          <el-button
            v-if="!sending"
            type="primary"
            class="send-btn"
            :icon="Promotion"
            @click="send"
          >发送</el-button>
          <el-button
            v-else
            type="danger"
            class="send-btn"
            :icon="VideoPause"
            @click="stopStream"
          >停止</el-button>
        </div>
      </div>
    </section>

    <!-- 图片预览大图 -->
    <el-image-viewer
      v-if="viewerVisible"
      :url-list="[viewerUrl]"
      @close="viewerVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, reactive } from 'vue'
import {
  Plus,
  Promotion,
  Picture,
  Close,
  Delete,
  ChatDotRound,
  CopyDocument,
  Microphone,
  Search,
  Download,
  VideoPause,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as convApi from '@/api/conversation'
import { getFileBlob } from '@/api/document'
import { uploadImage } from '@/api/upload'
import MarkdownContent from '@/components/MarkdownContent.vue'

const conversations = ref([])
const currentId = ref(null)
const messages = ref([])
const input = ref('')
const sending = ref(false)
const docMode = ref(true)
const webSearch = ref(false)
const ragCategory = ref('all')
// 面试拷问模式（grill-me）：仅面试分类下启用
const grillMode = ref(false)
// 分类选项：点击「文档」二字展开选择
const catOptions = [
  { label: '全部分类', value: 'all' },
  { label: '学习资料', value: 'material' },
  { label: '简历', value: 'resume' },
  { label: '面试经验', value: 'interview' },
]
const msgListRef = ref()

// 移动端会话列表抽屉开关
const showSideMobile = ref(false)

// 当前正在流式输出的助手消息 key（用于打字动效）+ 可中止的流对象
const streaming = ref('')
let currentStream = null

// 会话搜索
const searchQ = ref('')
const searching = ref(false)
const searchResults = ref([])

// 空态建议
const suggestions = [
  '帮我总结一下文档库里的学习资料',
  '给一份大厂前端面经提纲',
  '用 RAG 检索：什么是列表推导式？',
  '我的简历该怎么写更有竞争力？',
]

function pickSuggestion(s) {
  input.value = s
}

function toggleDocMode() {
  if (!sending.value) docMode.value = !docMode.value
}

function toggleWebSearch() {
  if (!sending.value) webSearch.value = !webSearch.value
}

function toggleGrillMode() {
  if (sending.value) return
  grillMode.value = !grillMode.value
  // 切换分类时若已开启拷问，自动关闭（拷问只在面试分类生效）
}

// 切换分类：离开面试分类时自动关闭拷问模式
function onCategoryChange() {
  if (ragCategory.value !== 'interview') grillMode.value = false
}

// 多模态：待发送的图片
const pendingImage = reactive({
  url: '',
  name: '',
  sizeText: '',
  raw: null,
})

// 大图预览
const viewerVisible = ref(false)
const viewerUrl = ref('')

async function loadConversations() {
  conversations.value = await convApi.listConversations()
}

async function newConversation() {
  const c = await convApi.createConversation({ title: '新对话', agent_type: 'rag' })
  conversations.value.unshift(c)
  selectConv(c)
}

async function removeConversation(c) {
  try {
    await ElMessageBox.confirm(
      `确定删除会话「${c.title}」吗？删除后不可恢复。`,
      '删除会话',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch (_) {
    return
  }
  try {
    await convApi.deleteConversation(c.id)
    conversations.value = conversations.value.filter((x) => x.id !== c.id)
    if (currentId.value === c.id) {
      currentId.value = null
      messages.value = []
    }
    ElMessage.success('会话已删除')
  } catch (e) {
    ElMessage.error('删除失败：' + (e?.message || String(e)))
  }
}

async function renameConv(c) {
  try {
    const { value } = await ElMessageBox.prompt('输入新的会话名称', '重命名会话', {
      inputValue: c.title,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValidator: (v) => (v && v.trim() ? true : '名称不能为空'),
    })
    await convApi.updateConversationTitle(c.id, value.trim())
    c.title = value.trim()
    ElMessage.success('已重命名')
  } catch (_) {
    // 取消或失败
  }
}

async function selectConv(c) {
  showSideMobile.value = false
  currentId.value = c.id
  messages.value = await convApi.listMessages(c.id)
  // 给每条消息加个稳定的渲染 key（流式追加时 message.id 可能为 null）
  messages.value.forEach((m, i) => (m._key = `m-${c.id}-${i}`))
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (msgListRef.value) msgListRef.value.scrollTop = msgListRef.value.scrollHeight
  })
}

// ---------- 会话搜索 ----------
let searchTimer = null
function onSearchInput() {
  clearTimeout(searchTimer)
  const q = searchQ.value.trim()
  if (!q) {
    clearSearch()
    return
  }
  searchTimer = setTimeout(() => doSearch(q), 300)
}

async function doSearch(q) {
  searching.value = true
  try {
    searchResults.value = await convApi.searchConversations(q)
  } catch (_) {
    searchResults.value = []
  } finally {
    searching.value = false
  }
}

function clearSearch() {
  searching.value = false
  searchResults.value = []
  loadConversations()
}

async function openSearchHit(h) {
  const c = conversations.value.find((x) => x.id === h.conversation_id)
  if (c) {
    await selectConv(c)
  } else {
    try {
      const c = await convApi.createConversation({ title: '新对话', agent_type: 'rag' })
      conversations.value.unshift(c)
      await selectConv(c)
    } catch (_) {}
  }
  searchQ.value = ''
  searching.value = false
  searchResults.value = []
}

// ---------- 导出当前会话为 Markdown ----------
function exportConversation() {
  if (!currentId.value || !messages.value.length) {
    ElMessage.warning('当前会话暂无内容')
    return
  }
  const c = conversations.value.find((x) => x.id === currentId.value)
  const title = (c && c.title) || '会话'
  const lines = ['# ' + title, '', '> 导出时间：' + new Date().toLocaleString('zh-CN'), '']
  messages.value.forEach((m) => {
    lines.push(`## ${m.role === 'user' ? '👤 用户' : '🤖 助手'}`)
    lines.push('')
    lines.push(m.content || '(仅图片)')
    lines.push('')
  })
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${title.replace(/[\\/:*?"<>|]/g, '_')}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
  ElMessage.success('已导出为 Markdown')
}

// ---------- 消息复制 ----------
async function copyText(text) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch (_) {
    ElMessage.warning('复制失败，请手动选择复制')
  }
}

// ---------- 朗读 ----------
function speak(text) {
  if (!('speechSynthesis' in window) || !text) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = 'zh-CN'
  u.rate = 1
  window.speechSynthesis.speak(u)
}

// ---------- 停止生成 ----------
function stopStream() {
  if (currentStream && currentStream.abort) currentStream.abort()
  sending.value = false
  streaming.value = ''
  currentStream = null
  scrollToBottom()
}

// ---------- 追问推荐 ----------
function buildFollowUps(lastUserText) {
  const base = (lastUserText || '').trim()
  const list = []
  if (base) {
    list.push(`关于「${base.length > 14 ? base.slice(0, 14) + '…' : base}」再详细讲讲`)
  }
  list.push('举个具体例子说明一下')
  list.push('有什么学习资料或面经可以参考吗')
  return list.slice(0, 3)
}

function askFollowUp(f) {
  if (sending.value) return
  input.value = f
  send()
}

// ---------- 多模态：图片上传 ----------
function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

async function handlePickImage(file) {
  // 限制单张 8MB
  if (file.size > 8 * 1024 * 1024) {
    ElMessage.warning('单张图片不能超过 8MB')
    return false
  }
  try {
    sending.value = true
    // request.js 拦截器已经把 ApiResponse.data 解包，这里直接拿到 {url, filename, size}
    const res = await uploadImage(file)
    pendingImage.url = res.url
    pendingImage.name = res.filename || file.name
    pendingImage.sizeText = formatSize(res.size || file.size)
    pendingImage.raw = file
    ElMessage.success('图片已就绪，输入问题后发送')
  } catch (e) {
    ElMessage.error('图片上传失败：' + (e?.message || String(e)))
    clearPendingImage()
  } finally {
    sending.value = false
  }
  // 返回 false 阻止 el-upload 自动上传（我们已经手动上传了）
  return false
}

function clearPendingImage() {
  pendingImage.url = ''
  pendingImage.name = ''
  pendingImage.sizeText = ''
  pendingImage.raw = null
}

function previewImage(url) {
  viewerUrl.value = url
  viewerVisible.value = true
}

// ---------- 工具调用可视化 ----------
function handleToolEvent(asstMsg, t) {
  if (!Array.isArray(asstMsg.tools)) asstMsg.tools = []
  if (t.status === 'start') {
    asstMsg.tools.push({ name: t.name, args: t.args, status: 'start', output: '' })
  } else if (t.status === 'done') {
    const running = asstMsg.tools.filter((x) => x.status === 'start')
    const last = running[running.length - 1]
    if (last) {
      last.status = 'done'
      last.output = t.output || ''
    }
  }
}

// ---------- 引用可点击下载 ----------
function isDownloadable(r) {
  return !!r && r.source === 'user' && r.doc_id > 0
}
function hasDownloadable(refs) {
  return Array.isArray(refs) && refs.some((r) => isDownloadable(r))
}
async function downloadRef(r) {
  try {
    const blob = await getFileBlob(r.doc_id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = r.doc_title || ('文档-' + r.doc_id)
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) {
    ElMessage.error('下载失败：' + (e?.message || String(e)))
  }
}

// ---------- 发送 ----------
async function send() {
  const text = input.value.trim()
  const imgUrl = pendingImage.url
  if (!text && !imgUrl) return
  if (sending.value) return
  if (!currentId.value) {
    try {
      await newConversation()
    } catch (e) {
      return
    }
  }

  // 1. 用户消息入列表 + 清空输入
  const userMsg = {
    _key: 'u-' + Date.now(),
    id: Date.now(),
    role: 'user',
    content: text || '(仅图片)',
    image_url: imgUrl || null,
  }
  messages.value.push(userMsg)
  input.value = ''
  clearPendingImage()
  sending.value = true
  await nextTick()
  scrollToBottom()

  // 2. 流式接收
  const asstMsg = reactive({ _key: 'a-' + Date.now(), id: null, role: 'assistant', content: '', refs: [], tools: [] })
  messages.value.push(asstMsg)
  streaming.value = asstMsg._key

  try {
    const stream = convApi.chatStream(
      {
        conversation_id: currentId.value,
        message: text || '请描述这张图片',
        image_url: imgUrl || undefined,
        use_rag: docMode.value,
        use_web_search: webSearch.value,
        rag_category: docMode.value ? ragCategory.value : 'all',
        agent_type: grillMode.value ? 'grill' : 'rag',
      },
      ({ event, payload }) => {
        if (event === 'start') {
          if (payload.conversation_id != null) currentId.value = payload.conversation_id
          asstMsg.refs = payload.refs || []
          // RAG 状态提示：检索链路故障 或 未检索到相关内容
          if (payload.rag_ok === false) {
            asstMsg._ragNotice = '知识库暂不可用，本次为通用回答'
          } else if (docMode.value && !asstMsg.refs.length) {
            asstMsg._ragNotice = '知识库未检索到相关内容，本次为通用回答'
          }
        } else if (event === 'delta') {
          asstMsg.content += payload.content || ''
          scrollToBottom()
        } else if (event === 'tool') {
          const t = payload && payload.tool
          if (t) handleToolEvent(asstMsg, t)
        } else if (event === 'end') {
          asstMsg.id = payload.message_id || null
          // 收尾：把仍在“调用中”的工具标记为已完成
          if (Array.isArray(asstMsg.tools)) {
            asstMsg.tools.forEach((x) => {
              if (x.status === 'start') x.status = 'done'
            })
          }
          // 追问推荐（仅在非中止且内容非空时生成）
          if (!payload.aborted && asstMsg.content) {
            asstMsg._followUps = buildFollowUps(text)
          }
          sending.value = false
          streaming.value = ''
          currentStream = null
          scrollToBottom()
          // 后台刷新左侧列表（标题/计数）
          setTimeout(() => loadConversations(), 100)
        } else if (event === 'error') {
          ElMessage.error(payload.detail || '对话出错')
          asstMsg.content += '\n\n[出错] ' + (payload.detail || '未知错误')
          sending.value = false
          streaming.value = ''
          currentStream = null
        }
      },
    )
    currentStream = stream
    await stream.promise
  } catch (e) {
    sending.value = false
    streaming.value = ''
    currentStream = null
  }
}

onMounted(async () => {
  await loadConversations()
  if (conversations.value.length) {
    await selectConv(conversations.value[0])
  }
})
</script>

<style scoped>
.chat-page {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 16px;
  align-items: stretch;
  height: 100%;
}

/* 左侧会话列表：玻璃面板 */
.side {
  flex: 0 0 22%;
  min-width: 210px;
  max-width: 320px;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(16px) saturate(160%);
  -webkit-backdrop-filter: blur(16px) saturate(160%);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  box-shadow: var(--card-shadow);
  overflow: hidden;
}
.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid #eef0f6;
  font-weight: 700;
}
.side-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.side-title {
  font-size: 14px;
}
.head-ico {
  border: 1px solid #e4e7f0 !important;
  color: #606266 !important;
}
.head-ico:hover {
  color: var(--brand-1) !important;
  border-color: var(--brand-1) !important;
}
.side-search {
  padding: 10px 12px 0;
}
.side-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}
.conv-item {
  padding: 11px 12px;
  border-radius: 12px;
  cursor: pointer;
  margin-bottom: 6px;
  transition: background 0.15s, transform 0.15s;
  display: flex;
  align-items: center;
  gap: 6px;
}
.conv-main {
  flex: 1;
  min-width: 0;
}
.conv-del {
  opacity: 0;
  transition: opacity 0.15s;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.92) !important;
  border: none !important;
  box-shadow: none !important;
  color: #f56c6c !important;
}
.conv-del:hover {
  background: #fef0f0 !important;
  color: #f56c6c !important;
}
.conv-item:hover .conv-del,
.conv-item.active .conv-del {
  opacity: 1;
}
.conv-item:hover {
  background: rgba(99, 102, 241, 0.08);
}
.conv-item.active {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  box-shadow: 0 6px 14px rgba(99, 102, 241, 0.3);
}
.conv-title {
  font-weight: 600;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.conv-meta {
  font-size: 12px;
  color: #9aa0b5;
  margin-top: 4px;
}
.conv-item.active .conv-meta {
  color: rgba(255, 255, 255, 0.75);
}

/* 搜索结果 */
.search-item {
  padding: 9px 11px;
  border-radius: 10px;
  margin-bottom: 6px;
  cursor: pointer;
  display: flex;
  gap: 8px;
  background: #f7f8fc;
  transition: background 0.15s;
}
.search-item:hover {
  background: rgba(99, 102, 241, 0.1);
}
.search-type {
  flex-shrink: 0;
  font-size: 11px;
  height: 20px;
  line-height: 20px;
  padding: 0 7px;
  border-radius: 999px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
}
.search-body {
  min-width: 0;
}
.search-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.search-snippet {
  font-size: 12px;
  color: #9aa0b5;
  margin-top: 2px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 右侧主区：玻璃面板 */
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(16px) saturate(160%);
  -webkit-backdrop-filter: blur(16px) saturate(160%);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  box-shadow: var(--card-shadow);
  overflow: hidden;
}

/* 消息列表 */
.msg-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.msg {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.msg.user {
  justify-content: flex-end;
}
.bubble-wrap {
  max-width: 72%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.msg.user .bubble-wrap {
  align-items: flex-end;
}
.msg.assistant .bubble-wrap {
  align-items: flex-start;
}

/* 头像 */
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.avatar.ai {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  box-shadow: 0 6px 14px rgba(99, 102, 241, 0.3);
}
.avatar.user {
  background: linear-gradient(135deg, #f472b6 0%, #a78bfa 100%);
  color: #fff;
  box-shadow: 0 6px 14px rgba(244, 114, 182, 0.28);
}

/* 图片消息 */
.msg-image img {
  max-width: 100%;
  max-height: 220px;
  border-radius: 12px;
  cursor: zoom-in;
  border: 1px solid #e4e7f0;
  display: block;
  box-shadow: var(--card-shadow);
}

/* 气泡 */
.bubble {
  padding: 12px 16px;
  border-radius: 16px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  font-size: 14px;
}
.msg.user .bubble {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  border-bottom-right-radius: 6px;
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.24);
}
.msg.assistant .bubble {
  background: #fff;
  color: var(--text-main);
  border: 1px solid #eef0f6;
  border-bottom-left-radius: 6px;
  box-shadow: 0 4px 14px rgba(31, 35, 41, 0.06);
}

/* 消息操作按钮（hover 显示） */
.msg-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
  align-self: flex-start;
}
.msg.user .bubble-wrap .msg-actions {
  align-self: flex-end;
}
.bubble-wrap:hover .msg-actions {
  opacity: 1;
}
.msg-actions .el-button {
  font-size: 12px;
  color: #9aa0b5;
  padding: 2px 6px;
}
.msg-actions .el-button:hover {
  color: var(--brand-1);
}

/* 打字动效 */
.is-thinking {
  display: flex;
  align-items: center;
  gap: 5px;
  min-height: 24px;
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--brand-1);
  animation: blink 1.2s infinite;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink {
  0%, 80%, 100% { opacity: 0.25; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}
.cursor {
  display: inline-block;
  width: 2px;
  height: 15px;
  margin-left: 2px;
  vertical-align: -2px;
  background: var(--brand-1);
  animation: caret 1s step-end infinite;
}
@keyframes caret {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 追问推荐 */
.follow-ups {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 2px 4px;
}
.fu-label {
  font-size: 12px;
  color: #9aa0b5;
}
.fu-chip {
  font-size: 12px;
  line-height: 1;
  padding: 5px 11px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e4e7f0;
  color: #4b5563;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 2px 6px rgba(99, 102, 241, 0.06);
}
.fu-chip:hover {
  border-color: var(--brand-1);
  color: var(--brand-1);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.16);
}

/* RAG 提示 + 参考来源 */
.rag-notice {
  font-size: 12px;
  color: #9aa0b5;
  line-height: 1.5;
  padding: 0 4px;
}
.refs {
  width: 100%;
  padding: 10px 12px;
  background: rgba(238, 242, 255, 0.8);
  border: 1px solid #e4e7f0;
  border-radius: 12px;
}
.refs-title {
  font-size: 12px;
  color: #6366f1;
  font-weight: 600;
  margin-bottom: 6px;
}
.ref-item {
  font-size: 12px;
  padding: 3px 0;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 6px;
}
.ref-idx {
  width: 18px;
  height: 18px;
  border-radius: 6px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ref-doc {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}
.ref-score {
  color: #c0c4cc;
}
.ref-src {
  flex-shrink: 0;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 999px;
  background: #eef0f6;
  color: #8a90a6;
}
.ref-clickable {
  cursor: pointer;
  border-radius: 8px;
  padding: 3px 6px;
  margin: 0 -6px;
  transition: background 0.15s;
}
.ref-clickable:hover {
  background: rgba(99, 102, 241, 0.1);
}
.ref-clickable:hover .ref-doc {
  color: var(--brand-1);
}

/* 工具调用可视化 chips */
.tool-chips {
  width: 100%;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #f5f6fa;
  border: 1px solid #e4e7f0;
  color: #606266;
}
.tool-chip.running {
  color: var(--brand-1);
  border-color: rgba(99, 102, 241, 0.4);
  background: rgba(238, 242, 255, 0.9);
}
.tool-icon {
  font-size: 11px;
}
.tool-name {
  font-weight: 600;
}
.tool-state {
  color: #9aa0b5;
}
.tool-state.ok {
  color: #10b981;
}

/* 空态欢迎 */
.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 40px 20px;
  text-align: center;
}
.welcome-logo {
  width: 72px;
  height: 72px;
  border-radius: 22px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 12px 30px rgba(99, 102, 241, 0.35);
}
.welcome-title {
  font-size: 22px;
  font-weight: 700;
}
.welcome-sub {
  color: var(--text-sub);
  font-size: 13px;
}
.suggests {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  max-width: 560px;
  margin-top: 8px;
}
.suggest {
  padding: 9px 16px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e4e7f0;
  color: #4b5563;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.06);
}
.suggest:hover {
  border-color: var(--brand-1);
  color: var(--brand-1);
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.16);
  transform: translateY(-2px);
}

/* 输入区 */
.composer {
  flex: 0 0 auto;
  border-top: 1px solid #eef0f6;
  padding: 12px 16px 14px;
  background: rgba(255, 255, 255, 0.55);
}
.pending-preview {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  margin-bottom: 10px;
  background: rgba(238, 242, 255, 0.8);
  border: 1px dashed #a5b4fc;
  border-radius: 10px;
}
.pending-preview img {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 8px;
}
.pending-meta {
  flex: 1;
  min-width: 0;
}
.pending-name {
  font-size: 13px;
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pending-size {
  font-size: 12px;
  color: #9aa0b5;
  margin-top: 2px;
}

.input-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}
.ico-btn {
  border: 1px solid #e4e7f0 !important;
  border-radius: 12px !important;
  background: #fff !important;
}
.ico-btn:hover {
  border-color: var(--brand-1) !important;
  color: var(--brand-1) !important;
}
.chat-input {
  flex: 1;
  min-height: 0;
}
.chat-input :deep(.el-textarea__inner) {
  border: none !important;
  box-shadow: none !important;
  border-radius: 0 !important;
  background: transparent !important;
  padding: 4px 2px 8px !important;
  font-size: 14px;
  line-height: 1.6;
}
.send-btn {
  height: 40px;
  padding: 0 20px;
  border-radius: 12px !important;
  font-size: 14px;
}

/* ---------- 输入框内嵌模式开关 ---------- */
.input-box {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid #e4e7f0;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.85);
  padding: 6px 8px 2px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.input-box:focus-within {
  border-color: rgba(99, 102, 241, 0.55);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.12);
}
.input-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.mode-chip {
  font-size: 12px;
  line-height: 1;
  padding: 4px 9px;
  border-radius: 999px;
  color: #9aa0b5;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  background: #f3f4f8;
  border: 1px solid transparent;
  transition: all 0.15s;
}
.mode-chip.on {
  color: var(--brand-1);
  font-weight: 600;
  background: rgba(238, 242, 255, 0.9);
  border-color: rgba(99, 102, 241, 0.4);
}
.cat-menu {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 0 4px;
  margin-bottom: 2px;
  border-top: 1px dashed #eef0f6;
}
.cat-opt {
  font-size: 12px;
  line-height: 1;
  padding: 5px 12px;
  border-radius: 999px;
  color: #606266;
  background: #f5f6fa;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  transition: all 0.15s;
}
.cat-opt:hover {
  color: var(--brand-1);
}
.cat-opt.active {
  color: #fff;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  box-shadow: 0 4px 10px rgba(99, 102, 241, 0.25);
}

/* ---------- 消息入场动效 ---------- */
.msg {
  animation: msgIn 0.3s ease;
}
@keyframes msgIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ---------- 移动端会话按钮 / 遮罩 ---------- */
.mobile-menu-btn {
  display: none;
  position: absolute;
  left: 14px;
  top: 14px;
  z-index: 40;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border: 1px solid var(--glass-border);
  color: var(--brand-1);
  background: rgba(255, 255, 255, 0.85);
}
.side-mask {
  display: none;
  position: absolute;
  inset: 0;
  z-index: 29;
  background: rgba(15, 23, 42, 0.35);
  backdrop-filter: blur(2px);
}

/* ---------- 窄屏适配 ---------- */
@media (max-width: 900px) {
  .side {
    flex: 0 0 30%;
    min-width: 170px;
  }
}

@media (max-width: 768px) {
  .chat-page {
    position: relative;
    gap: 0;
  }
  .side {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 78%;
    max-width: 300px;
    z-index: 30;
    transform: translateX(-105%);
    transition: transform 0.25s ease;
  }
  .side.mobile-open {
    transform: translateX(0);
  }
  .mobile-menu-btn,
  .side-mask {
    display: flex;
  }
  .side-mask {
    display: block;
  }
  .bubble-wrap {
    max-width: 84%;
  }
  .msg-list {
    padding: 14px 12px;
    gap: 14px;
  }
  .composer {
    padding: 10px;
  }
  .input-row {
    gap: 8px;
  }
  .send-btn {
    padding: 0 14px;
  }
  .welcome-title {
    font-size: 18px;
  }
  .welcome-sub {
    font-size: 12px;
  }
  .msg-actions {
    opacity: 1;
  }
}

@media (max-width: 480px) {
  .bubble {
    font-size: 13.5px;
    padding: 10px 13px;
  }
}
</style>
