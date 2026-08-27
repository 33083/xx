<template>
  <div class="profile-page">
    <div class="profile-card glass">
      <div class="profile-head">
        <el-avatar
          :size="72"
          :src="form.avatar || undefined"
          class="profile-avatar"
          icon="UserFilled"
        />
        <div class="head-info">
          <div class="head-name">{{ displayName }}</div>
          <div class="head-role">
            <el-tag :type="userStore.isAdmin ? 'danger' : 'primary'" size="small" effect="light">
              {{ userStore.isAdmin ? '管理员' : '学生' }}
            </el-tag>
            <span class="head-uid">ID: {{ profile?.id }}</span>
          </div>
        </div>
      </div>

      <el-divider />

      <el-form label-position="left" label-width="90px" class="profile-form">
        <el-form-item label="用户名">
          <el-input :model-value="profile?.username" disabled />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickname" placeholder="设置你的昵称" maxlength="64" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="头像链接">
          <el-input v-model="form.avatar" placeholder="https://...（可选）" />
        </el-form-item>
        <el-form-item label="注册时间">
          <el-input :model-value="createdText" disabled />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存修改</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getMe, updateMe } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const profile = ref(null)
const saving = ref(false)
const form = reactive({ nickname: '', email: '', avatar: '' })

const displayName = computed(
  () => form.nickname || profile.value?.username || userStore.username || '用户',
)

const createdText = computed(() => {
  if (!profile.value?.created_at) return '-'
  const d = new Date(profile.value.created_at)
  if (Number.isNaN(d.getTime())) return String(profile.value.created_at)
  return d.toLocaleString('zh-CN', { hour12: false })
})

async function load() {
  const data = await getMe()
  profile.value = data
  form.nickname = data.nickname || ''
  form.email = data.email || ''
  form.avatar = data.avatar || ''
}

async function save() {
  const email = form.email.trim()
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    ElMessage.warning('请输入正确的邮箱格式')
    return
  }
  // 空值不提交，避免把必填字段覆盖为空
  const payload = {}
  if (form.nickname.trim()) payload.nickname = form.nickname.trim()
  if (form.avatar.trim()) payload.avatar = form.avatar.trim()
  if (email) payload.email = email
  if (!Object.keys(payload).length) {
    ElMessage.info('没有需要保存的修改')
    return
  }
  saving.value = true
  try {
    const data = await updateMe(payload)
    profile.value = data
    if (data.username) userStore.username = data.username
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.message || String(e)))
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.profile-page {
  max-width: 640px;
  margin: 0 auto;
  padding: 8px 0;
}
.profile-card {
  padding: 28px 32px;
}
.profile-head {
  display: flex;
  align-items: center;
  gap: 18px;
}
.profile-avatar {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.3);
  flex-shrink: 0;
}
.head-info {
  min-width: 0;
}
.head-name {
  font-size: 20px;
  font-weight: 700;
}
.head-role {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}
.head-uid {
  font-size: 13px;
  color: #9aa0b5;
}
.profile-form {
  max-width: 460px;
}
.profile-form :deep(.el-input__wrapper) {
  border-radius: 10px !important;
}
</style>
