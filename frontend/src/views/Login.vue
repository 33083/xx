<template>
  <div class="login-page">
    <!-- 背景装饰光斑 -->
    <div class="bg-blob blob-1"></div>
    <div class="bg-blob blob-2"></div>
    <div class="bg-blob blob-3"></div>

    <div class="wrap">
      <!-- 左侧品牌区 -->
      <div class="brand">
        <div class="logo">
          <el-icon :size="30"><Promotion /></el-icon>
        </div>
        <h1 class="grad-text">大学生学习与求职智能助手</h1>
        <p class="slogan">让 AI 陪伴你的学习与求职每一步</p>
        <div class="chips">
          <span class="chip">📚 文档知识库</span>
          <span class="chip">🧠 RAG 精准回答</span>
          <span class="chip">🖼️ 多模态理解</span>
          <span class="chip">🛠️ 技能市场</span>
        </div>
      </div>

      <!-- 右侧玻璃卡片 -->
      <div class="glass card">
        <el-tabs v-model="tab" stretch>
          <el-tab-pane label="登录" name="login" />
          <el-tab-pane label="注册" name="register" />
        </el-tabs>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @submit.prevent="onSubmit"
        >
          <el-form-item v-if="tab === 'register'" label="用户名" prop="username">
            <el-input v-model="form.username" placeholder="3-64 位，字母数字下划线" :prefix-icon="User" />
          </el-form-item>
          <el-form-item v-if="tab === 'register'" label="邮箱" prop="email">
            <el-input v-model="form.email" placeholder="example@stu.edu.cn" :prefix-icon="Message" />
          </el-form-item>
          <el-form-item v-else label="账号" prop="account">
            <el-input v-model="form.account" placeholder="用户名或邮箱" :prefix-icon="User" />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              show-password
              placeholder="至少 6 位"
              :prefix-icon="Lock"
              @keyup.enter="onSubmit"
            />
          </el-form-item>

          <el-button type="primary" class="submit" :loading="loading" @click="onSubmit">
            {{ tab === 'login' ? '进入智能助手' : '创建账号' }}
          </el-button>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Message } from '@element-plus/icons-vue'
import * as authApi from '@/api/auth'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const tab = ref('login')
const loading = ref(false)
const formRef = ref()

const form = reactive({
  username: '',
  email: '',
  account: '',
  password: '',
})

const rules = computed(() => {
  const common = { password: [{ required: true, message: '请输入密码', trigger: 'blur' }] }
  if (tab.value === 'login') {
    return {
      ...common,
      account: [{ required: true, message: '请输入账号', trigger: 'blur' }],
    }
  }
  return {
    ...common,
    username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
    email: [{ required: true, message: '请输入邮箱', trigger: 'blur' }],
  }
})

watch(tab, () => {
  formRef.value?.clearValidate()
})

async function onSubmit() {
  await formRef.value?.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const fn = tab.value === 'login' ? authApi.login : authApi.register
      let payload
      if (tab.value === 'login') {
        payload = { account: form.account, password: form.password }
      } else {
        payload = {
          username: form.username,
          email: form.email,
          password: form.password,
        }
      }
      const data = await fn(payload)
      userStore.setAuth(data)
      ElMessage.success(tab.value === 'login' ? '登录成功' : '注册成功')
      router.push(route.query.redirect || '/')
    } catch (e) {
      // 拦截器已弹错误提示
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-page {
  position: relative;
  height: 100vh;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(150deg, #eef2ff 0%, #f4f1ff 45%, #fdeeff 100%);
}

/* 背景光斑 */
.bg-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.55;
  pointer-events: none;
}
.blob-1 {
  width: 420px;
  height: 420px;
  background: #a5b4fc;
  top: -120px;
  left: -80px;
}
.blob-2 {
  width: 380px;
  height: 380px;
  background: #c4b5fd;
  bottom: -100px;
  right: -60px;
}
.blob-3 {
  width: 260px;
  height: 260px;
  background: #f9a8d4;
  bottom: 18%;
  left: 22%;
  opacity: 0.35;
}

.wrap {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 64px;
  padding: 24px;
}

/* 品牌区 */
.brand {
  max-width: 460px;
}
.logo {
  width: 64px;
  height: 64px;
  border-radius: 18px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 24px rgba(99, 102, 241, 0.35);
  margin-bottom: 22px;
}
.brand h1 {
  font-size: 30px;
  line-height: 1.35;
  margin: 0 0 12px;
  letter-spacing: 0.5px;
}
.slogan {
  color: var(--text-sub);
  font-size: 15px;
  margin: 0 0 24px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.chip {
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--glass-border);
  color: #4b5563;
  font-size: 13px;
  backdrop-filter: blur(8px);
}

/* 卡片 */
.card {
  width: 400px;
  padding: 26px 28px;
}
.title {
  margin: 0 0 8px;
  font-size: 22px;
  text-align: center;
  color: #303133;
}
.submit {
  width: 100%;
  margin-top: 8px;
  height: 42px;
  font-size: 15px;
}

@media (max-width: 900px) {
  .wrap {
    flex-direction: column;
    gap: 28px;
  }
  .brand {
    text-align: center;
    max-width: 100%;
  }
  .brand .logo {
    margin: 0 auto 18px;
  }
  .chips {
    justify-content: center;
  }
  .card {
    width: 100%;
    max-width: 400px;
  }
}
</style>
