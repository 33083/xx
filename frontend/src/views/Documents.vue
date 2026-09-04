<template>
  <div class="docs-page">
    <el-card>
      <template #header>
        <div class="head">
          <span>文档库</span>
          <div class="head-actions">
            <el-input
              v-model="keyword"
              class="search-input"
              placeholder="搜索标题 / 备注"
              clearable
              :prefix-icon="Search"
              @keyup.enter="loadList(true)"
              @clear="loadList(true)"
            />
            <el-button :icon="Download" :disabled="!list.length" @click="exportList">导出列表</el-button>
            <el-upload
              :show-file-list="false"
              :auto-upload="false"
              multiple
              accept=".pdf,.txt,.md,.markdown,.pptx,.doc,.docx"
              :on-change="onPick"
              :disabled="uploading"
            >
              <el-button type="primary" :icon="Upload" :loading="uploading">上传文档</el-button>
            </el-upload>
          </div>
        </div>
      </template>

      <!-- 空态：拖拽上传引导 -->
      <div v-if="!loading && !list.length" class="docs-empty">
        <el-upload
          class="empty-upload"
          drag
          multiple
          :show-file-list="false"
          :auto-upload="false"
          accept=".pdf,.txt,.md,.markdown,.pptx,.doc,.docx"
          :on-change="onPick"
          :disabled="uploading"
        >
          <el-icon :size="52" class="upload-big"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖拽文件到此处，或 <em>点击上传</em></div>
          <div class="el-upload__tip">
            支持 PDF / TXT / MD / PPTX / DOC / DOCX，可多选，将自动解析并构建知识库
          </div>
        </el-upload>
      </div>

      <!-- 列表 -->
      <template v-else>
        <el-radio-group v-model="category" style="margin-bottom: 12px">
          <el-radio-button label="material">学习资料</el-radio-button>
          <el-radio-button label="resume">简历</el-radio-button>
          <el-radio-button label="interview">面试经验</el-radio-button>
        </el-radio-group>

        <div style="margin-bottom: 12px">
          <el-button
            size="small"
            type="danger"
            plain
            :icon="Delete"
            :disabled="!selection.length"
            @click="removeMany"
          >
            批量删除{{ selection.length ? ` (${selection.length})` : '' }}
          </el-button>
        </div>

        <el-table :data="list" border stripe v-loading="loading" @selection-change="selection = $event">
          <el-table-column type="selection" width="48" />
          <el-table-column label="标题" min-width="200">
            <template #default="{ row }">
              <el-link type="primary" :underline="false" @click="openPreview(row)">{{ row.title }}</el-link>
            </template>
          </el-table-column>
          <el-table-column prop="file_type" label="类型" width="80" />
          <el-table-column label="大小" width="100">
            <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
          </el-table-column>
          <el-table-column label="切片数" width="80">
            <template #default="{ row }">{{ row.chunk_count || 0 }}</template>
          </el-table-column>
          <el-table-column prop="category" label="分类" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.category === 'material'">资料</el-tag>
              <el-tag v-else-if="row.category === 'resume'" type="success">简历</el-tag>
              <el-tag v-else-if="row.category === 'interview'" type="warning">面试经验</el-tag>
              <span v-else>{{ row.category }}</span>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button size="small" text type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
              <el-button size="small" text type="danger" :icon="Delete" :loading="row._deleting" @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="hasMore" class="load-more">
          <el-button :loading="loading" @click="loadList()">加载更多</el-button>
        </div>
      </template>
    </el-card>

    <!-- 预览弹窗 -->
    <el-dialog v-model="previewVisible" :title="previewTitle" width="82%" top="4vh" destroy-on-close class="preview-dialog">
      <div v-loading="previewLoading" :loading-text="previewLoadingText" class="preview-body">
        <div v-if="previewError" class="preview-error" role="alert">
          <el-alert
            :title="previewError"
            type="error"
            show-icon
            :closable="false"
            description="提示：大文件预览需等待解析，超时可重试；Word/PPT 可先在本地打开查看，也可以到聊天界面让 AI 提炼摘要。"
          />
        </div>
        <!-- PDF：object + iframe 两层渲染，失败提示放 iframe 外面（避免 <p> 作为 <iframe> 子节点违反 HTML 规范触发 Vite hydrate warning） -->
        <template v-if="!previewLoading && previewUrl">
          <object :data="previewUrl" type="application/pdf" class="preview-frame" aria-label="PDF预览">
            <iframe :src="previewUrl" class="preview-frame"></iframe>
          </object>
          <div class="preview-empty" role="note">
            ⚠️ 如果上方预览区域是一片空白，说明浏览器的 PDF 阅读器被 IDM 或扩展拦截了。请直接点击右下角的「下载此文件」按钮，用本地 WPS / Adobe Reader 打开。
          </div>
        </template>
        <pre v-else-if="!previewLoading && previewText" class="preview-text">{{ previewText }}</pre>
        <el-empty v-else-if="!previewLoading && !previewError" description="暂不支持预览该类型，点击下方按钮直接下载。" />
      </div>
      <template #footer>
        <div class="preview-footer">
          <span class="preview-hint">
            <template v-if="previewFileType === 'pdf'">浏览器内嵌 PDF 阅读器</template>
            <template v-else-if="previewFileType === 'docx' || previewFileType === 'doc'">Word 文档（仅文本预览，原格式会丢失）</template>
            <template v-else-if="previewFileType === 'pptx'">PPT 演示文稿（仅文本预览）</template>
            <template v-else>文档预览</template>
            ：预览效果不好可直接下载原始文件 ↓
          </span>
          <div>
            <el-button @click="previewVisible = false">关闭</el-button>
            <el-button type="primary" :icon="Download" :disabled="!currentDocId" :loading="downloadingFile" @click="downloadCurrentFile">下载此文件</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editVisible" title="编辑文档" width="480px">
      <el-form label-width="60px">
        <el-form-item label="标题">
          <el-input v-model="editForm.title" maxlength="255" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.description" type="textarea" :rows="3" maxlength="5000" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingEdit" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { Search, Edit, Upload, Delete, Download, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as docApi from '@/api/document'

const category = ref('material')
const keyword = ref('')
const list = ref([])
const loading = ref(false)
const uploading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = 20
const hasMore = ref(false)
const selection = ref([])
const pendingQueue = ref([])

// 预览
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewLoadingText = ref('加载中...')
const previewTitle = ref('')
const previewUrl = ref('')
const previewText = ref('')
const previewError = ref('')
const previewFileType = ref('')
const currentDocId = ref(null)
const downloadingFile = ref(false)
let openingPreview = false
let currentObjectUrl = ''

// 编辑
const editVisible = ref(false)
const savingEdit = ref(false)
const editForm = ref({ id: null, title: '', description: '' })

function formatSize(b) {
  if (!b) return '0 B'
  if (b < 1024) return b + ' B'
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB'
  return (b / 1024 / 1024).toFixed(1) + ' MB'
}

function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  if (Number.isNaN(+d)) return t
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadList(reset = false) {
  if (loading.value) return
  loading.value = true
  const targetPage = reset ? 1 : page.value
  try {
    const data = await docApi.listDocuments({
      page: targetPage,
      page_size: pageSize,
      category: category.value,
      keyword: keyword.value || undefined,
    })
    list.value = reset ? data.items : [...list.value, ...data.items]
    total.value = data.total
    page.value = targetPage + 1
    hasMore.value = list.value.length < total.value
  } catch (e) {
    // request 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function uploadOne(raw) {
  const res = await docApi.uploadDocument(raw, { category: category.value })
  ElMessage.success(`已上传：${res.title}（${res.chunk_count} 个切片）`)
  if (res.category === category.value) {
    if (keyword.value) {
      await loadList(true)
    } else {
      list.value.unshift({
        id: res.id,
        title: res.title,
        file_type: raw.name.split('.').pop(),
        file_size: raw.size,
        category: res.category,
        chunk_count: res.chunk_count,
        created_at: new Date().toISOString(),
      })
      total.value += 1
      hasMore.value = list.value.length < total.value
    }
  }
}

async function processQueue() {
  if (uploading.value) return
  uploading.value = true
  try {
    while (pendingQueue.value.length) {
      const raw = pendingQueue.value.shift()
      try {
        await uploadOne(raw)
      } catch (e) {
        // request 拦截器已提示（含重复文件 400）
      }
    }
  } finally {
    uploading.value = false
  }
}

function onPick(file) {
  const raw = file.raw
  if (!raw) return
  pendingQueue.value.push(raw)
  processQueue()
}

async function remove(row) {
  await ElMessageBox.confirm('删除后向量库中对应的文档切片也会一并清除，确认继续？', '提示', {
    type: 'warning',
  })
  row._deleting = true
  try {
    await docApi.deleteDocument(row.id)
    list.value = list.value.filter((d) => d.id !== row.id)
    ElMessage.success('已删除')
  } finally {
    row._deleting = false
  }
}

async function removeMany() {
  const ids = selection.value.map((r) => r.id)
  if (!ids.length) return
  await ElMessageBox.confirm(`确认删除选中的 ${ids.length} 个文档？向量库中对应的切片也会一并清除。`, '提示', {
    type: 'warning',
  })
  try {
    await Promise.all(ids.map((id) => docApi.deleteDocument(id)))
  } catch (e) {
    // request 拦截器已提示
  }
  selection.value = []
  ElMessage.success('已删除')
  await loadList(true)
}

// 导出当前筛选列表为 CSV
function exportList() {
  if (!list.value.length) {
    ElMessage.warning('当前列表为空')
    return
  }
  const head = ['ID', '标题', '类型', '大小(B)', '分类', '切片数', '创建时间']
  const rows = list.value.map((d) => [
    d.id,
    d.title,
    d.file_type,
    d.file_size,
    d.category,
    d.chunk_count || 0,
    formatTime(d.created_at),
  ])
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const csv = '\uFEFF' + [head, ...rows].map((r) => r.map(esc).join(',')).join('\r\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `文档库_${category.value}_${Date.now()}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
  ElMessage.success('已导出 CSV')
}

async function openPreview(row) {
  if (openingPreview) return
  openingPreview = true
  previewVisible.value = true
  previewLoading.value = true
  previewLoadingText.value = '正在加载预览...'
  previewTitle.value = row.title
  previewUrl.value = ''
  previewText.value = ''
  previewError.value = ''
  currentDocId.value = row.id
  previewFileType.value = row.file_type
  if (currentObjectUrl) {
    URL.revokeObjectURL(currentObjectUrl)
    currentObjectUrl = ''
  }
  try {
    // 第一步：拿预览元信息（返回 { file_type, preview_url?, text? }）
    previewLoadingText.value = '正在解析文档内容...'
    const data = await docApi.previewDocument(row.id)
    if (data.file_type === 'pdf') {
      // PDF：统一走带 token 的 axios Blob 下载，再用 ObjectURL 嵌入 iframe。
      // 注意：不能把 /documents/{id}/file 当作 url 直接塞给 iframe，因为 iframe 发的原生 HTTP GET
      //      不会带 Authorization 头，会触发 401 → 被 request.js 误判成"网络已断开"。
      previewLoadingText.value = '正在加载 PDF 文件...'
      const blob = await docApi.getFileBlob(row.id)
      currentObjectUrl = URL.createObjectURL(blob)
      previewUrl.value = currentObjectUrl
    } else {
      // 其他格式：返回 text（Word/TXT/MD/PPTX 等）
      previewText.value = data.text || ''
    }
  } catch (e) {
    previewError.value = e.friendlyMsg || e.message || '预览失败，请稍后重试'
  } finally {
    previewLoading.value = false
    previewLoadingText.value = '加载中...'
    openingPreview = false
  }
}

function openEdit(row) {
  editForm.value = { id: row.id, title: row.title, description: row.description || '' }
  editVisible.value = true
}

async function saveEdit() {
  if (!editForm.value.title.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }
  savingEdit.value = true
  try {
    await docApi.updateDocument(editForm.value.id, {
      title: editForm.value.title.trim(),
      description: editForm.value.description,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    const row = list.value.find((d) => d.id === editForm.value.id)
    if (row) {
      row.title = editForm.value.title.trim()
      row.description = editForm.value.description
    }
  } catch (e) {
    // request 拦截器已提示
  } finally {
    savingEdit.value = false
  }
}

async function downloadCurrentFile() {
  if (!currentDocId.value) return
  downloadingFile.value = true
  try {
    const blob = await docApi.getFileBlob(currentDocId.value)
    const safeTitle = (previewTitle.value || 'document').replace(/[\\/:*?"<>|]/g, '_')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = safeTitle
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(a.href), 3000)
    ElMessage.success('已开始下载')
  } catch (e) {
    previewError.value = '下载失败：' + (e.friendlyMsg || e.message || '请稍后重试')
  } finally {
    downloadingFile.value = false
  }
}

function onScroll() {
  const el = document.documentElement
  if (el.scrollTop + window.innerHeight >= el.scrollHeight - 120 && hasMore.value && !loading.value) {
    loadList()
  }
}

watch(category, () => loadList(true))

onMounted(() => {
  loadList(true)
  window.addEventListener('scroll', onScroll, { passive: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
  if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl)
})
</script>

<style scoped>
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.search-input {
  width: 220px;
}
.load-more {
  margin-top: 12px;
  text-align: center;
}
.preview-body {
  min-height: 200px;
}
.preview-error {
  margin-bottom: 12px;
}
.preview-frame {
  width: 100%;
  height: 70vh;
  border: none;
  background: #fff;
  border-radius: 4px;
}
.preview-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.preview-hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.preview-empty {
  padding: 40px 16px;
  color: #e6a23c;
  text-align: center;
  border: 1px dashed var(--el-color-warning-light-5);
  border-radius: 6px;
}
.preview-text {
  max-height: 65vh;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 6px;
  font-size: 13px;
}
/* 空态拖拽上传 */
.docs-empty {
  padding: 10px 0 6px;
}
.empty-upload :deep(.el-upload-dragger) {
  border-radius: 16px;
  border-style: dashed;
  border-color: #a5b4fc;
  background: rgba(238, 242, 255, 0.35);
  padding: 48px 20px;
  transition: border-color 0.2s, background 0.2s, transform 0.15s;
}
.empty-upload :deep(.el-upload-dragger:hover) {
  border-color: var(--brand-1);
  background: rgba(238, 242, 255, 0.6);
  transform: translateY(-2px);
}
.upload-big {
  color: var(--brand-1);
  margin-bottom: 10px;
}
</style>
