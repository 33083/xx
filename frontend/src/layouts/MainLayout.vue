<template>
  <el-container class="layout">
    <el-aside :width="isCollapse ? '72px' : '220px'" class="aside">
      <div class="logo">
        <div class="logo-icon">
          <el-icon :size="20"><Promotion /></el-icon>
        </div>
        <span v-show="!isCollapse" class="title">学习求职助手</span>
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="isCollapse"
        router
        class="side-menu"
      >
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>智能对话</template>
        </el-menu-item>
        <el-menu-item index="/documents">
          <el-icon><FolderOpened /></el-icon>
          <template #title>文档库</template>
        </el-menu-item>
        <el-menu-item index="/skills">
          <el-icon><MagicStick /></el-icon>
          <template #title>技能市场</template>
        </el-menu-item>
        <el-menu-item v-if="userStore.isAdmin" index="/admin">
          <el-icon><Setting /></el-icon>
          <template #title>管理后台</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="left">
          <div class="collapse-btn glass-ico" @click="isCollapse = !isCollapse">
            <el-icon :size="18">
              <Fold v-if="!isCollapse" />
              <Expand v-else />
            </el-icon>
          </div>
          <div class="collapse-btn glass-ico" title="切换深浅色" @click="toggleTheme">
            <el-icon :size="18">
              <Moon v-if="!isDark" />
              <Sunny v-else />
            </el-icon>
          </div>
          <span class="page-title grad-text">{{ route.meta.title }}</span>
        </div>
        <el-dropdown @command="onCommand">
          <span class="user">
            <el-avatar :size="32" class="user-avatar" icon="UserFilled" />
            <span class="name">{{ userStore.username || '用户' }}</span>
            <el-icon><CaretBottom /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人资料</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Moon, Sunny } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isCollapse = ref(false)
const isDark = ref(document.documentElement.classList.contains('dark'))

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

function applyResponsive() {
  isCollapse.value = window.innerWidth <= 768
}
onMounted(() => {
  applyResponsive()
  window.addEventListener('resize', applyResponsive)
})
onBeforeUnmount(() => window.removeEventListener('resize', applyResponsive))

async function onCommand(cmd) {
  if (cmd === 'logout') {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', { type: 'warning' })
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  } else if (cmd === 'profile') {
    router.push('/profile')
  }
}
</script>

<style scoped>
.layout {
  height: 100vh;
}

/* 渐变侧边栏 */
.aside {
  background: linear-gradient(180deg, #4f46e5 0%, #7c3aed 100%);
  transition: width 0.2s;
  overflow: hidden;
  box-shadow: 4px 0 20px rgba(79, 70, 229, 0.18);
}
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  color: #fff;
}
.logo-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.title {
  font-size: 16px;
  font-weight: 700;
  white-space: nowrap;
  letter-spacing: 0.5px;
}

/* 菜单：透明底，白色文字，圆角高亮 */
.side-menu {
  border-right: none !important;
  background: transparent !important;
  padding: 8px;
}
.side-menu :deep(.el-menu-item) {
  border-radius: 12px;
  margin: 4px 0;
  height: 48px;
  color: rgba(255, 255, 255, 0.82) !important;
  font-size: 14px;
}
.side-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.14) !important;
  color: #fff !important;
}
.side-menu :deep(.el-menu-item.is-active) {
  background: rgba(255, 255, 255, 0.22) !important;
  color: #fff !important;
  font-weight: 600;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.25);
}
.side-menu :deep(.el-menu-item.is-active) .el-icon {
  color: #fff;
}

/* 玻璃头部 */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(14px) saturate(160%);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
  border-bottom: 1px solid var(--glass-border);
}
.left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.collapse-btn {
  cursor: pointer;
  color: var(--text-sub);
}
.glass-ico {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
}
.glass-ico:hover {
  background: rgba(99, 102, 241, 0.18);
}
.page-title {
  font-size: 17px;
  font-weight: 700;
}
.user {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}
.user-avatar {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}
.name {
  font-size: 14px;
  font-weight: 500;
}

.main {
  padding: 20px;
}

/* ---------- 窄屏适配 ---------- */
@media (max-width: 768px) {
  .aside {
    width: 64px !important;
    flex-basis: 64px !important;
    max-width: 64px !important;
  }
  .logo {
    padding: 0;
    justify-content: center;
  }
  .side-menu {
    padding: 8px 6px;
  }
  .header {
    padding: 0 12px;
  }
  .collapse-btn {
    display: none;
  }
  .name {
    display: none;
  }
  .page-title {
    font-size: 15px;
  }
  .main {
    padding: 12px;
  }
}
</style>
