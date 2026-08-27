<template>
  <div class="market">
    <!-- 顶部：搜索框 + 分类筛选 -->
    <div class="toolbar">
      <el-input
        v-model="q"
        placeholder="搜索技能名/描述/分类"
        clearable
        :prefix-icon="Search"
        class="search-input"
        @input="onSearchDebounced"
      />
      <el-radio-group v-model="cat" @change="load">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button v-for="c in categories" :key="c.value" :label="c.value">{{ c.label }}</el-radio-button>
      </el-radio-group>
      <span class="stats">共 {{ tools.length }} 个技能</span>
    </div>

    <el-empty v-if="!loading && !tools.length" description="没有匹配的技能" />

    <div v-loading="loading" class="grid">
      <div v-for="t in tools" :key="t.skill_key" class="card" :class="{ installed: t.installed, unavailable: !t.available }">
        <div class="card-head">
          <div class="icon">
            <el-icon :size="22"><component :is="iconComp(t.icon)" /></el-icon>
          </div>
          <div class="meta">
            <div class="name">{{ t.name }}</div>
            <div class="cat">
              <el-tag size="small" effect="plain" type="info">{{ t.category_label }}</el-tag>
              <el-tag size="small" effect="plain" type="warning" style="margin-left: 4px">{{ t.source }}</el-tag>
            </div>
          </div>
        </div>

        <div class="desc">{{ t.description }}</div>

        <div class="deps" v-if="!t.available">
          <el-icon><Warning /></el-icon>
          <span>依赖未装好：{{ t.requirements.join(', ') }}</span>
        </div>

        <div class="actions">
          <el-button
            v-if="!t.installed"
            type="primary"
            :icon="Download"
            :disabled="!t.available"
            @click="emitInstall(t)"
          >
            安装
          </el-button>
          <template v-else>
            <el-tag type="success" effect="dark" :icon="Check">已安装</el-tag>
            <el-button
              type="danger"
              plain
              size="small"
              :icon="Delete"
              @click="emitUninstall(t)"
            >
              卸载
            </el-button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import * as ElIcons from '@element-plus/icons-vue'
import { Search, Download, Delete, Check, Warning } from '@element-plus/icons-vue'
import { listMarket } from '@/api/skill'

const props = defineProps({ refreshKey: { type: Number, default: 0 } })
const emit = defineEmits(['install', 'uninstall'])

const q = ref('')
const cat = ref('')
const tools = ref([])
const loading = ref(false)

// 分类（前端写死，避免初始为空）
const categories = [
  { value: 'search', label: '网络搜索' },
  { value: 'academic', label: '学术辅助' },
  { value: 'compute', label: '计算与代码' },
]

let _timer = null
function onSearchDebounced() {
  clearTimeout(_timer)
  _timer = setTimeout(load, 250)
}

function iconComp(name) {
  return ElIcons[name] || ElIcons.MagicStick
}

async function load() {
  loading.value = true
  try {
    tools.value = await listMarket({ q: q.value, category: cat.value })
  } finally {
    loading.value = false
  }
}

function emitInstall(t) {
  emit('install', { skill_key: t.skill_key, name: t.name })
}
function emitUninstall(t) {
  emit('uninstall', { skill_key: t.skill_key, name: t.name })
}

onMounted(load)
watch(() => props.refreshKey, load)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.search-input {
  width: 320px;
  max-width: 100%;
}
.stats {
  margin-left: auto;
  font-size: 13px;
  color: var(--text-sub);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}
.card {
  border: 1px solid var(--glass-border);
  border-radius: 14px;
  padding: 18px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(12px) saturate(150%);
  -webkit-backdrop-filter: blur(12px) saturate(150%);
  box-shadow: var(--card-shadow);
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: box-shadow 0.2s, transform 0.2s, border-color 0.2s;
}
.card:hover {
  box-shadow: var(--card-shadow-hover);
  transform: translateY(-2px);
  border-color: #c7d2fe;
}
.card.installed {
  border-color: #b3e19d;
  background: rgba(240, 249, 235, 0.72);
}
.card.unavailable {
  opacity: 0.7;
}
.card-head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.icon {
  width: 46px;
  height: 46px;
  border-radius: 13px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 6px 14px rgba(99, 102, 241, 0.25);
}
.meta {
  flex: 1;
  min-width: 0;
}
.name {
  font-weight: 600;
  font-size: 15px;
}
.cat {
  margin-top: 6px;
}
.desc {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  min-height: 36px;
}
.deps {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #e6a23c;
  background: #fdf6ec;
  padding: 6px 10px;
  border-radius: 8px;
}
.actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
}
</style>
