<template>
  <div class="admin-page">
    <el-tabs v-model="tab">
      <!-- 系统概览 -->
      <el-tab-pane label="系统概览" name="stats">
        <el-row :gutter="14">
          <el-col v-for="c in statCards" :key="c.key" :xs="12" :sm="8" :md="6">
            <div class="stat-card">
              <div class="stat-icon" :style="{ background: c.color }">
                <el-icon :size="20"><component :is="c.icon" /></el-icon>
              </div>
              <div class="stat-body">
                <div class="stat-num">{{ c.value }}</div>
                <div class="stat-label">{{ c.label }}</div>
              </div>
            </div>
          </el-col>
        </el-row>
        <el-card class="status-card">
          <template #header><span>运行状态</span></template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="用户总数">{{ stats.users }}</el-descriptions-item>
            <el-descriptions-item label="活跃用户">{{ stats.active_users }}</el-descriptions-item>
            <el-descriptions-item label="管理员">{{ stats.admins }}</el-descriptions-item>
            <el-descriptions-item label="文档数">{{ stats.documents }}</el-descriptions-item>
            <el-descriptions-item label="会话数">{{ stats.conversations }}</el-descriptions-item>
            <el-descriptions-item label="消息数">{{ stats.messages }}</el-descriptions-item>
            <el-descriptions-item label="公共库切片">{{ stats.shared_chunks }}</el-descriptions-item>
            <el-descriptions-item label="后端状态"><el-tag type="success">运行中</el-tag></el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-tab-pane>

      <!-- 用户管理 -->
      <el-tab-pane label="用户管理" name="users">
        <el-card>
          <el-table :data="users" border stripe v-loading="loadingUsers">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="username" label="用户名" min-width="120" />
            <el-table-column prop="email" label="邮箱" min-width="200" />
            <el-table-column prop="role" label="角色" width="100">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">
                  {{ row.role }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'warning'">
                  {{ row.is_active ? '正常' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="注册时间" min-width="160">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="170" fixed="right">
              <template #default="{ row }">
                <el-button
                  size="small"
                  text
                  :disabled="row.id === meId"
                  @click="toggleActive(row)"
                >{{ row.is_active ? '禁用' : '启用' }}</el-button>
                <el-button
                  size="small"
                  text
                  type="danger"
                  :disabled="row.id === meId"
                  :loading="row._deleting"
                  @click="del(row)"
                >删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 技能配置 -->
      <el-tab-pane label="技能配置" name="skills">
        <el-card>
          <el-empty description="复用「技能市场」页面统一管理" />
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  UserFilled,
  User,
  Files,
  ChatDotRound,
  Message,
  CollectionTag,
  CircleCheck,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const meId = ref(null)

const tab = ref('stats')
const users = ref([])
const loadingUsers = ref(false)
const stats = ref({
  users: 0,
  active_users: 0,
  admins: 0,
  documents: 0,
  conversations: 0,
  messages: 0,
  shared_chunks: 0,
})

const statCards = computed(() => [
  { key: 'users', label: '用户总数', value: stats.value.users, color: 'linear-gradient(135deg,#6366f1,#8b5cf6)', icon: UserFilled },
  { key: 'active', label: '活跃用户', value: stats.value.active_users, color: 'linear-gradient(135deg,#10b981,#34d399)', icon: CircleCheck },
  { key: 'admins', label: '管理员', value: stats.value.admins, color: 'linear-gradient(135deg,#f59e0b,#fbbf24)', icon: User },
  { key: 'docs', label: '文档数', value: stats.value.documents, color: 'linear-gradient(135deg,#3b82f6,#60a5fa)', icon: Files },
  { key: 'convs', label: '会话数', value: stats.value.conversations, color: 'linear-gradient(135deg,#8b5cf6,#a78bfa)', icon: ChatDotRound },
  { key: 'msgs', label: '消息数', value: stats.value.messages, color: 'linear-gradient(135deg,#ec4899,#f472b6)', icon: Message },
  { key: 'chunks', label: '公共库切片', value: stats.value.shared_chunks, color: 'linear-gradient(135deg,#14b8a6,#2dd4bf)', icon: CollectionTag },
])

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-CN')
}

async function loadStats() {
  try {
    stats.value = await request.get('/users/stats')
  } catch (_) {
    // 拦截器已提示
  }
}

async function loadUsers() {
  loadingUsers.value = true
  try {
    users.value = await request.get('/users')
  } catch (_) {
    // 拦截器已提示
  } finally {
    loadingUsers.value = false
  }
}

async function toggleActive(row) {
  const next = !row.is_active
  try {
    await ElMessageBox.confirm(
      `确定${next ? '启用' : '禁用'}用户 ${row.username}？`,
      '提示',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' },
    )
  } catch (_) {
    return
  }
  try {
    await request.patch(`/users/${row.id}/active`, { is_active: next })
    row.is_active = next
    ElMessage.success(next ? '已启用' : '已禁用')
    loadStats()
  } catch (e) {
    ElMessage.error('操作失败：' + (e?.message || String(e)))
  }
}

async function del(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除用户 ${row.username}？其文档与会话将一并删除，此操作不可恢复`,
      '危险操作',
      { type: 'error', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch (_) {
    return
  }
  row._deleting = true
  try {
    await request.delete(`/users/${row.id}`)
    users.value = users.value.filter((u) => u.id !== row.id)
    ElMessage.success('已删除')
    loadStats()
  } catch (e) {
    ElMessage.error('删除失败：' + (e?.message || String(e)))
  } finally {
    row._deleting = false
  }
}

onMounted(async () => {
  try {
    const me = await userStore.fetchMe()
    meId.value = me ? me.id : null
  } catch (_) {}
  loadStats()
  loadUsers()
})
</script>

<style scoped>
.admin-page {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(14px) saturate(150%);
  -webkit-backdrop-filter: blur(14px) saturate(150%);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  box-shadow: var(--card-shadow);
  padding: 8px 20px 20px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid #eef0f6;
  box-shadow: 0 4px 14px rgba(31, 35, 41, 0.05);
  margin-bottom: 14px;
  transition: transform 0.15s, box-shadow 0.15s;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.14);
}
.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-num {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--text-main);
}
.stat-label {
  font-size: 12px;
  color: #9aa0b5;
  margin-top: 2px;
}
.status-card {
  border-radius: 14px;
  border: 1px solid #eef0f6;
}
</style>
