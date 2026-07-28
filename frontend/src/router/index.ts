import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/login',
            name: 'login',
            component: () => import('@/views/Login.vue'),
        },
        {
            path: '/',
            component: () => import('@/layouts/MainLayout.vue'),
            redirect: '/dashboard',
            children: [
                {
                    path: 'dashboard',
                    name: 'dashboard',
                    component: () => import('@/views/Dashboard.vue'),
                    meta: { title: '仪表盘' },
                },
                {
                    path: 'projects',
                    name: 'projects',
                    component: () => import('@/views/Projects.vue'),
                    meta: { title: '项目管理' },
                },
                {
                    path: 'tasks',
                    name: 'tasks',
                    component: () => import('@/views/Tasks.vue'),
                    meta: { title: '任务管理' },
                },
                {
                    path: 'executions',
                    name: 'executions',
                    component: () => import('@/views/Executions.vue'),
                    meta: { title: '执行记录' },
                },
                {
                    path: 'proxies',
                    name: 'proxies',
                    component: () => import('@/views/Proxies.vue'),
                    meta: { title: '代理池' },
                },
                {
                    path: 'nodes',
                    name: 'nodes',
                    component: () => import('@/views/Nodes.vue'),
                    meta: { title: '节点管理' },
                },
                {
                    path: 'statistics',
                    name: 'statistics',
                    component: () => import('@/views/Statistics.vue'),
                    meta: { title: '统计报表' },
                },
                {
                    path: 'audits',
                    name: 'audits',
                    component: () => import('@/views/Audits.vue'),
                    meta: { title: '审计日志' },
                },
                {
                    path: 'notifications',
                    name: 'notifications',
                    component: () => import('@/views/Notifications.vue'),
                    meta: { title: '通知配置' },
                },
                {
                    path: 'roles',
                    name: 'roles',
                    component: () => import('@/views/Roles.vue'),
                    meta: { title: '角色管理' },
                },
                {
                    path: 'venvs',
                    name: 'venvs',
                    component: () => import('@/views/Venvs.vue'),
                    meta: { title: '虚拟环境' },
                },
            ],
        },
    ],
})

// 路由守卫
router.beforeEach((to, _from, next) => {
    const token = localStorage.getItem('token')
    if (to.path !== '/login' && !token) {
        next('/login')
    } else {
        next()
    }
})

export default router
