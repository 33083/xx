import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // Element Plus 全量引入 + 全量图标（约 960KB minify / gzip 约 296KB），整体是
    // 业务可接受的首屏总 gzip 体积（~465KB）。由于 Element Plus 全量组件天然体积较大，
    // 仅靠 manualChunks 拆分后仍会超 500KB 默认阈值，因此适度放宽；如要进一步缩小，
    // 可改走 unplugin-auto-import + unplugin-vue-components 的按需引入方案。
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        manualChunks(id) {
          // 第三方依赖统一从 node_modules 里识别，按"包名前缀"分组拆 chunk
          if (id.includes('node_modules')) {
            // 1) Element Plus 组件库 + 官方图标包：体积最大，单独成一个 chunk
            if (
              id.includes('element-plus') ||
              id.includes('@element-plus/icons-vue')
            ) {
              return 'element-plus'
            }
            // 2) Vue 全家桶（核心框架/路由/状态管理）：稳定少变，独立缓存
            if (
              id.includes('/vue/') ||
              id.includes('/vue@') ||
              id.includes('vue-router') ||
              id.includes('pinia')
            ) {
              return 'vue-vendor'
            }
            // 3) 请求库、工具库等其它第三方依赖
            if (id.includes('axios')) {
              return 'utils-vendor'
            }
            // 剩余 node_modules 统一落到默认 vendor
            return 'vendor'
          }
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      // 前端开发期把 /api 代理到 FastAPI
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // 上传的图片静态资源（后端 mount 在 /uploads）
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // WebSocket 流式对话
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
