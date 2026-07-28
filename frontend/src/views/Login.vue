<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { NCard, NForm, NFormItem, NInput, NButton, useMessage } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const message = useMessage()
const authStore = useAuthStore()
const loading = ref(false)

const formData = reactive({
  username: '',
  password: '',
})

const handleLogin = async () => {
  if (!formData.username || !formData.password) {
    message.warning('请输入用户名和密码')
    return
  }

  loading.value = true
  try {
    await authStore.login(formData.username, formData.password)
    message.success('登录成功')
    router.push('/dashboard')
  } catch (error: any) {
    message.error(error.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <div class="login-content">
      <!-- 左侧品牌区 -->
      <div class="login-brand">
        <div class="brand-logo">
          <svg viewBox="0 0 24 24" width="48" height="48" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
          </svg>
        </div>
        <h1 class="brand-title">CrawlOps</h1>
        <p class="brand-desc">分布式采集任务的一体化控制台</p>
      </div>

      <!-- 右侧登录表单 -->
      <n-card class="login-card">
        <h2 class="login-title">欢迎登录</h2>
        <n-form>
          <n-form-item label="用户名">
            <n-input
              v-model:value="formData.username"
              placeholder="请输入用户名"
              size="large"
            />
          </n-form-item>
          <n-form-item label="密码">
            <n-input
              v-model:value="formData.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              @keyup.enter="handleLogin"
            />
          </n-form-item>
          <n-button
            type="primary"
            :loading="loading"
            @click="handleLogin"
            block
            size="large"
            style="margin-top: 8px"
          >
            登 录
          </n-button>
        </n-form>
        <div class="login-hint">
          本地首次启动：<code>admin</code> / <code>123456</code><br>
          对外部署前请在 <code>docker-compose.yml</code> 中修改密码。
        </div>
      </n-card>
    </div>

    <!-- 底部版权 -->
    <div class="login-footer">
      © 2026 CrawlOps Contributors
    </div>
  </div>
</template>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #165DFF 0%, #0E42D2 100%);
  padding: 20px;
}

.login-content {
  display: flex;
  align-items: center;
  gap: 80px;
}

.login-brand {
  color: #fff;
  text-align: center;
}

.brand-logo {
  width: 80px;
  height: 80px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24px;
}

.brand-title {
  font-size: 32px;
  font-weight: 600;
  margin: 0 0 8px;
}

.brand-desc {
  font-size: 14px;
  opacity: 0.8;
  margin: 0;
}

.login-card {
  width: 380px;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

.login-title {
  font-size: 20px;
  font-weight: 600;
  color: #1D2129;
  margin: 0 0 24px;
  text-align: center;
}

.login-hint {
  margin-top: 16px;
  text-align: center;
  color: #86909C;
  font-size: 12px;
}

.login-footer {
  position: fixed;
  bottom: 24px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 12px;
}

/* 响应式 */
@media (max-width: 768px) {
  .login-content {
    flex-direction: column;
    gap: 32px;
  }

  .login-brand {
    display: none;
  }

  .login-card {
    width: 100%;
    max-width: 380px;
  }
}
</style>
