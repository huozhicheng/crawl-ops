<script setup lang="ts">
import { ref, h, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  NLayout,
  NLayoutSider,
  NLayoutHeader,
  NLayoutContent,
  NMenu,
  NIcon,
  NDropdown,
  NAvatar,
  NSpace,
  NBreadcrumb,
  NBreadcrumbItem,
  NSelect,
  NButton,
} from 'naive-ui'
import {
  HomeOutline,
  FolderOutline,
  TimeOutline,
  ListOutline,
  GlobeOutline,
  ServerOutline,
  DocumentTextOutline,
  NotificationsOutline,
  PeopleOutline,
  TerminalOutline,
  RefreshOutline,
} from '@vicons/ionicons5'

const router = useRouter()
const route = useRoute()
const collapsed = ref(false)

const isDashboard = computed(() => route.name === 'dashboard')

// Dashboard 刷新控制
const refreshInterval = ref(30)
const lastRefreshTime = ref('')
const refreshOptions = [
  { label: '关闭', value: 0 },
  { label: '10秒', value: 10 },
  { label: '30秒', value: 30 },
  { label: '60秒', value: 60 },
]

// 提供给子组件
import { provide } from 'vue'
provide('refreshInterval', refreshInterval)
provide('lastRefreshTime', lastRefreshTime)

const triggerRefresh = () => {
  lastRefreshTime.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  // 触发自定义事件
  window.dispatchEvent(new CustomEvent('dashboard-refresh'))
}

// 当前选中的菜单项，根据路由名称自动高亮
const activeMenu = computed(() => route.name as string)

const menuOptions = [
  {
    label: '仪表盘',
    key: 'dashboard',
    icon: () => h(NIcon, null, { default: () => h(HomeOutline) }),
  },
  {
    label: '任务中心',
    key: 'task-center',
    icon: () => h(NIcon, null, { default: () => h(ListOutline) }),
    children: [
      {
        label: '项目管理',
        key: 'projects',
        icon: () => h(NIcon, null, { default: () => h(FolderOutline) }),
      },
      {
        label: '任务管理',
        key: 'tasks',
        icon: () => h(NIcon, null, { default: () => h(TimeOutline) }),
      },
      {
        label: '执行记录',
        key: 'executions',
        icon: () => h(NIcon, null, { default: () => h(TerminalOutline) }),
      },
    ]
  },
  {
    label: '资源管理',
    key: 'resources',
    icon: () => h(NIcon, null, { default: () => h(ServerOutline) }),
    children: [
      {
        label: '节点管理',
        key: 'nodes',
        icon: () => h(NIcon, null, { default: () => h(ServerOutline) }),
      },
      {
        label: '虚拟环境',
        key: 'venvs',
        icon: () => h(NIcon, null, { default: () => h(TerminalOutline) }),
      },
      {
        label: '代理池',
        key: 'proxies',
        icon: () => h(NIcon, null, { default: () => h(GlobeOutline) }),
      },
    ]
  },
  {
    label: '系统管理',
    key: 'system',
    icon: () => h(NIcon, null, { default: () => h(PeopleOutline) }),
    children: [
      {
        label: '审计日志',
        key: 'audits',
        icon: () => h(NIcon, null, { default: () => h(DocumentTextOutline) }),
      },
      {
        label: '通知配置',
        key: 'notifications',
        icon: () => h(NIcon, null, { default: () => h(NotificationsOutline) }),
      },
      {
        label: '角色管理',
        key: 'roles',
        icon: () => h(NIcon, null, { default: () => h(PeopleOutline) }),
      },
    ]
  },
]

const handleMenuUpdate = (key: string) => {
  router.push({ name: key })
}

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('refreshToken')
  router.push('/login')
}
</script>

<template>
  <n-layout has-sider class="main-layout">
    <!-- 侧边栏 -->
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="220"
      :collapsed="collapsed"
      @collapse="collapsed = true"
      @expand="collapsed = false"
      show-trigger
      class="sidebar"
    >
      <!-- Logo -->
      <div class="logo">
        <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
        </svg>
        <span v-if="!collapsed" class="logo-text">CrawlOps</span>
      </div>

      <!-- 菜单 -->
      <n-menu
        :value="activeMenu"
        :collapsed="collapsed"
        :collapsed-width="64"
        :collapsed-icon-size="20"
        :options="menuOptions"
        :indent="24"
        @update:value="handleMenuUpdate"
      />
    </n-layout-sider>

    <!-- 主内容区 -->
    <n-layout class="content-layout">
      <!-- 顶栏 -->
      <n-layout-header bordered class="header">
        <div class="header-left">
          <n-breadcrumb v-if="route.meta?.title">
            <n-breadcrumb-item>{{ route.meta.title }}</n-breadcrumb-item>
          </n-breadcrumb>
        </div>
        <div class="header-right">
          <!-- Dashboard 刷新控件 -->
          <n-space v-if="isDashboard" align="center" :size="8" style="margin-right: 24px">
            <span class="refresh-time">上次刷新于 {{ lastRefreshTime || '—' }}</span>
            <n-select v-model:value="refreshInterval" :options="refreshOptions"
              size="small" style="width: 80px" />
            <n-button size="small" quaternary @click="triggerRefresh">
              <template #icon><n-icon :component="RefreshOutline" /></template>
            </n-button>
          </n-space>
          <n-dropdown
            trigger="click"
            :options="[{ label: '退出登录', key: 'logout' }]"
            @select="handleLogout"
          >
            <n-space align="center" class="user-info">
              <n-avatar round size="small" :style="{ backgroundColor: '#165DFF' }">A</n-avatar>
              <span class="username">Admin</span>
            </n-space>
          </n-dropdown>
        </div>
      </n-layout-header>

      <!-- 页面内容 -->
      <n-layout-content class="page-content">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<style scoped>
.main-layout {
  height: 100vh;
  background-color: #F2F3F5;
}

.sidebar {
  background-color: #fff;
}

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-bottom: 1px solid #E5E6EB;
  color: #1D2129;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: #1D2129;
}

.content-layout {
  background-color: #F2F3F5;
}

.header {
  height: 56px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #fff;
}

.header-left {
  display: flex;
  align-items: center;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.user-info:hover {
  background-color: #F2F3F5;
}

.username {
  font-size: 14px;
  color: #4E5969;
}

.refresh-time {
  font-size: 12px;
  color: #C9CDD4;
}

.page-content {
  padding: 20px;
  background-color: #F2F3F5;
  min-height: calc(100vh - 56px);
}
</style>
