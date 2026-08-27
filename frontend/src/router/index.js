import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/chat',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'chat',
        name: 'chat',
        component: () => import('@/views/Chat.vue'),
        meta: { title: '智能对话' },
      },
      {
        path: 'documents',
        name: 'documents',
        component: () => import('@/views/Documents.vue'),
        meta: { title: '文档库' },
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('@/views/Profile.vue'),
        meta: { title: '个人资料' },
      },
      {
        path: 'skills',
        name: 'skills',
        component: () => import('@/views/Skills.vue'),
        meta: { title: '技能市场' },
      },
      {
        path: 'admin',
        name: 'admin',
        component: () => import('@/views/Admin.vue'),
        meta: { title: '管理后台', requiresAdmin: true },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局守卫：未登录跳登录页
router.beforeEach((to) => {
  const userStore = useUserStore()
  if (to.meta.requiresAuth && !userStore.isLogin) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && userStore.isLogin) {
    return '/'
  }
  if (to.meta.requiresAdmin && !userStore.isAdmin) {
    return { name: 'chat' }
  }
})

export default router
