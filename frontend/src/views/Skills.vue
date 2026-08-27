<template>
  <div class="skills-page">
    <el-tabs v-model="activeTab" class="tabs">
      <el-tab-pane label="我的技能" name="mine">
        <MySkills :refresh-key="refreshKey" @toggle="onToggleMine" />
      </el-tab-pane>

      <el-tab-pane label="技能市场" name="market">
        <MarketView :refresh-key="refreshKey" @install="onInstall" @uninstall="onUninstall" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import MySkills from '@/components/skills/MySkills.vue'
import MarketView from '@/components/skills/MarketView.vue'
import {
  toggleSkill,
  installMarketSkill,
  uninstallMarketSkill,
} from '@/api/skill'

const activeTab = ref('mine')
const refreshKey = ref(0) // 子组件 watch 这个值，变了就重新拉数据

function bump() {
  refreshKey.value += 1
}

async function onToggleMine({ skill_key, enabled }) {
  try {
    await toggleSkill(skill_key, enabled)
    ElMessage.success(`${enabled ? '已启用' : '已禁用'}：${skill_key}`)
    bump()
  } catch (e) {
    ElMessage.error('切换失败：' + (e?.message || String(e)))
    bump()
  }
}

async function onInstall({ skill_key, name }) {
  try {
    await installMarketSkill(skill_key)
    ElMessage.success(`已安装并启用：${name}`)
    bump()
  } catch (e) {
    ElMessage.error('安装失败：' + (e?.message || String(e)))
  }
}

async function onUninstall({ skill_key, name }) {
  try {
    await uninstallMarketSkill(skill_key)
    ElMessage.success(`已卸载：${name}`)
    bump()
  } catch (e) {
    ElMessage.error('卸载失败：' + (e?.message || String(e)))
  }
}
</script>

<style scoped>
.skills-page {
  padding: 0;
}
.tabs {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(14px) saturate(150%);
  -webkit-backdrop-filter: blur(14px) saturate(150%);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  box-shadow: var(--card-shadow);
  padding: 8px 20px 20px;
  min-height: 100%;
}
.tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: #eef0f6;
}
.tabs :deep(.el-tabs__content) {
  min-height: 400px;
}
</style>
