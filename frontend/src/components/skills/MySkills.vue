<template>
  <div class="my-skills">
    <el-empty v-if="!loading && !skills.length" description="尚未安装任何技能" />

    <div v-loading="loading" class="grid">
      <div v-for="s in skills" :key="s.skill_key" class="card" :class="{ disabled: !s.enabled }">
        <div class="card-head">
          <div class="icon">
            <el-icon :size="20"><component :is="iconComp(s.icon)" /></el-icon>
          </div>
          <div class="meta">
            <div class="name">
              {{ s.name }}
              <el-tag v-if="s.source === 'langchain_community'" type="warning" size="small" effect="plain">市场</el-tag>
              <el-tag v-else-if="s.source === 'langchain_experimental'" type="warning" size="small" effect="plain">市场</el-tag>
              <el-tag v-else type="info" size="small" effect="plain">内置</el-tag>
            </div>
            <div class="cat">{{ s.category_label }}</div>
          </div>
          <el-switch
            v-model="s.enabled"
            :loading="s._toggling"
            @change="(v) => onToggle(s, v)"
          />
        </div>
        <div class="desc">{{ s.description }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import * as ElIcons from '@element-plus/icons-vue'
import { listSkills } from '@/api/skill'

const props = defineProps({ refreshKey: { type: Number, default: 0 } })
const emit = defineEmits(['toggle'])

const skills = ref([])
const loading = ref(false)

function iconComp(name) {
  // 找不到图标就用 MagicStick 兜底
  return ElIcons[name] || ElIcons.MagicStick
}

async function load() {
  loading.value = true
  try {
    skills.value = await listSkills()
  } finally {
    loading.value = false
  }
}

async function onToggle(s, enabled) {
  s._toggling = true
  try {
    // 乐观更新，由父组件真正发请求；失败由父组件 bump 重新拉
    emit('toggle', { skill_key: s.skill_key, enabled, name: s.name })
  } finally {
    s._toggling = false
  }
}

onMounted(load)
watch(() => props.refreshKey, load)
</script>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.card {
  border: 1px solid var(--glass-border);
  border-radius: 14px;
  padding: 16px 18px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(12px) saturate(150%);
  -webkit-backdrop-filter: blur(12px) saturate(150%);
  box-shadow: var(--card-shadow);
  transition: box-shadow 0.2s, transform 0.2s, border-color 0.2s;
}
.card:hover {
  box-shadow: var(--card-shadow-hover);
  transform: translateY(-2px);
  border-color: #c7d2fe;
}
.card.disabled {
  opacity: 0.55;
}
.card-head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
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
  font-size: 14px;
}
.name .el-tag {
  margin-left: 6px;
}
.cat {
  font-size: 12px;
  color: var(--text-sub);
  margin-top: 2px;
}
.desc {
  font-size: 13px;
  color: #606266;
  margin-top: 10px;
  line-height: 1.6;
}
</style>
