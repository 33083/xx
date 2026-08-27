<template>
  <div ref="rootEl" class="md-body" v-html="html"></div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

const props = defineProps({ content: { type: String, default: '' } })
const rootEl = ref()

function escapeHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

marked.use({
  gfm: true,
  breaks: true,
  renderer: {
    code({ text, lang, escaped }) {
      const language = (lang || '').split(/\s+/)[0] || ''
      let highlighted = escapeHtml(text)
      let cls = ''
      if (language && hljs.getLanguage(language)) {
        try {
          highlighted = hljs.highlight(text, { language, ignoreIllegals: true }).value
          cls = ' language-' + language
        } catch (_) {
          highlighted = escapeHtml(text)
        }
      }
      const encoded = encodeURIComponent(text)
      return (
        '<div class="code-block">' +
        '<div class="code-head">' +
        '<span class="code-lang">' + (language || 'text') + '</span>' +
        '<button type="button" class="code-copy" data-code="' + encoded + '">复制</button>' +
        '</div>' +
        '<pre><code class="hljs' + cls + '">' + highlighted + '</code></pre>' +
        '</div>'
      )
    },
  },
})

const html = computed(() => marked.parse(props.content || '') || '')

// 代码块复制按钮事件委托
watch(html, () => {
  nextTick(() => {
    if (!rootEl.value) return
    rootEl.value.querySelectorAll('.code-copy').forEach((btn) => {
      btn.onclick = (e) => {
        e.stopPropagation()
        const code = decodeURIComponent(btn.dataset.code || '')
        navigator.clipboard.writeText(code).then(() => {
          btn.textContent = '已复制'
          setTimeout(() => (btn.textContent = '复制'), 1500)
        })
      }
    })
  })
})
</script>

<style scoped>
.md-body {
  line-height: 1.75;
  font-size: 14px;
  word-break: break-word;
}
.md-body :deep(p) {
  margin: 0.5em 0;
}
.md-body :deep(p:first-child) {
  margin-top: 0;
}
.md-body :deep(p:last-child) {
  margin-bottom: 0;
}
.md-body :deep(h1),
.md-body :deep(h2),
.md-body :deep(h3),
.md-body :deep(h4) {
  margin: 0.8em 0 0.4em;
  font-weight: 700;
  line-height: 1.4;
}
.md-body :deep(h1) { font-size: 1.25em; }
.md-body :deep(h2) { font-size: 1.15em; }
.md-body :deep(h3) { font-size: 1.05em; }
.md-body :deep(h4) { font-size: 1em; }
.md-body :deep(ul),
.md-body :deep(ol) {
  padding-left: 1.4em;
  margin: 0.4em 0;
}
.md-body :deep(li) {
  margin: 0.2em 0;
}
.md-body :deep(a) {
  color: var(--brand-1, #6366f1);
  text-decoration: none;
}
.md-body :deep(a:hover) {
  text-decoration: underline;
}
.md-body :deep(blockquote) {
  margin: 0.5em 0;
  padding: 4px 12px;
  border-left: 3px solid var(--brand-1, #6366f1);
  background: rgba(99, 102, 241, 0.06);
  border-radius: 0 8px 8px 0;
  color: #606266;
}
.md-body :deep(table) {
  border-collapse: collapse;
  margin: 0.6em 0;
  width: 100%;
  display: block;
  overflow-x: auto;
}
.md-body :deep(th),
.md-body :deep(td) {
  border: 1px solid #e4e7f0;
  padding: 6px 10px;
  text-align: left;
  font-size: 13px;
}
.md-body :deep(th) {
  background: #f5f6fa;
  font-weight: 600;
}
.md-body :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}
.md-body :deep(code) {
  background: rgba(99, 102, 241, 0.08);
  color: #6d28d9;
  padding: 2px 5px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
  font-size: 13px;
}
.md-body :deep(pre) {
  background: #f8f9fc;
  border: 1px solid #eef0f6;
  border-radius: 10px;
  padding: 12px 14px;
  overflow-x: auto;
  margin: 0.6em 0;
}
.md-body :deep(pre code) {
  background: transparent;
  color: #383a42;
  padding: 0;
  font-size: 13px;
  line-height: 1.6;
}
.md-body :deep(.code-block) {
  margin: 0.6em 0;
  border: 1px solid #eef0f6;
  border-radius: 10px;
  overflow: hidden;
}
.md-body :deep(.code-block pre) {
  margin: 0;
  border: none;
  border-radius: 0;
}
.md-body :deep(.code-head) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f5f6fa;
  padding: 4px 12px;
  font-size: 12px;
  color: #9aa0b5;
}
.md-body :deep(.code-copy) {
  border: none;
  background: transparent;
  color: #6366f1;
  cursor: pointer;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 6px;
}
.md-body :deep(.code-copy:hover) {
  background: rgba(99, 102, 241, 0.1);
}
.md-body :deep(hr) {
  border: none;
  border-top: 1px solid #eef0f6;
  margin: 0.8em 0;
}
</style>
