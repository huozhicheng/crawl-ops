import api from './request'

// 认证相关
export const authApi = {
    login: (data: { username: string; password: string }) =>
        api.post('/auth/login', data),
    logout: () => api.post('/auth/logout'),
    refresh: (data: { refresh_token: string }) =>
        api.post('/auth/refresh', data),
    me: () => api.get('/auth/me'),
}

// 用户相关
export const userApi = {
    list: (params?: any) => api.get('/users', { params }),
    get: (id: number) => api.get(`/users/${id}`),
    create: (data: any) => api.post('/users', data),
    update: (id: number, data: any) => api.put(`/users/${id}`, data),
    delete: (id: number) => api.delete(`/users/${id}`),
}

// 项目相关
export const projectApi = {
    list: (params?: any) => api.get('/projects', { params }),
    get: (id: number) => api.get(`/projects/${id}`),
    create: (data: any) => api.post('/projects', data),
    update: (id: number, data: any) => api.put(`/projects/${id}`, data),
    delete: (id: number) => api.delete(`/projects/${id}`),
}

// 任务相关
export const taskApi = {
    list: (params?: any) => api.get('/tasks', { params }),
    get: (id: number) => api.get(`/tasks/${id}`),
    create: (data: any) => api.post('/tasks', data),
    update: (id: number, data: any) => api.put(`/tasks/${id}`, data),
    delete: (id: number) => api.delete(`/tasks/${id}`),
    run: (id: number) => api.post(`/tasks/${id}/run`),
    updateStatus: (id: number, status: number) =>
        api.put(`/tasks/${id}/status`, { status }),
}

// 执行记录相关
export const executionApi = {
    list: (params?: any) => api.get('/executions', { params }),
    get: (id: number) => api.get(`/executions/${id}`),
    logs: (id: number) => api.get(`/executions/${id}/logs`),
    stop: (id: number) => api.post(`/executions/${id}/stop`),
}

// 节点相关
export const nodeApi = {
    list: (params?: any) => api.get('/nodes', { params }),
    create: (data: any) => api.post('/nodes', data),
    update: (id: number, data: any) => api.put(`/nodes/${id}`, data),
    delete: (id: number) => api.delete(`/nodes/${id}`),
    ping: (id: number) => api.post(`/nodes/${id}/ping`),
}

// 代理池相关
export const proxyApi = {
    list: (params?: any) => api.get('/proxies', { params }),
    get: () => api.get('/proxies/get'),
    create: (data: any) => api.post('/proxies', data),
    import: (data: { proxies: string[]; protocol: string }) =>
        api.post('/proxies/import', data),
    delete: (id: number) => api.delete(`/proxies/${id}`),
    verify: (id: number) => api.post(`/proxies/${id}/verify`),
    verifyAll: () => api.post('/proxies/verify-all'),
    feedback: (id: number, success: boolean) =>
        api.post(`/proxies/${id}/feedback`, { success }),
}

// 仪表盘相关
export const dashboardApi = {
    getOverview: () => api.get('/dashboard/overview'),
    getTrend: (days?: number) => api.get('/dashboard/trend', { params: { days } }),
    getRecentExecutions: (limit?: number) =>
        api.get('/dashboard/recent-executions', { params: { limit } }),
    getFailures: (limit?: number) =>
        api.get('/dashboard/failures', { params: { limit } }),
    getNodesMonitor: () => api.get('/dashboard/nodes-monitor'),
    getRisks: () => api.get('/dashboard/risks'),
    getUpcoming: (limit?: number) => api.get('/dashboard/upcoming', { params: { limit } }),
    getNodeHistory: (nodeId: number, limit?: number) =>
        api.get('/dashboard/node-history', { params: { node_id: nodeId, limit } }),
}

// 虚拟环境相关
export const venvsApi = {
    list: (params?: any) => api.get('/venvs', { params }),
    get: (id: number) => api.get(`/venvs/${id}`),
    create: (data: any) => api.post('/venvs', data),
    delete: (id: number) => api.delete(`/venvs/${id}`),
    listPackages: (id: number) => api.get(`/venvs/${id}/packages`),
    installPackage: (id: number, package_name: string) => api.post(`/venvs/${id}/packages`, { package: package_name }),
    installPackagesBatch: (id: number, packages: string[]) => api.post(`/venvs/${id}/packages/batch`, { packages }),
    uploadRequirements: (id: number, file: File) => {
        const formData = new FormData()
        formData.append('file', file)
        return api.post(`/venvs/${id}/packages/upload-requirements`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        })
    },
}

// 审计日志相关
export const auditsApi = {
    list: (params?: any) => api.get('/audits', { params }),
}

// 统计报表相关
export const statisticsApi = {
    trend: (days: number = 7) => api.get('/statistics/trend', { params: { days } }),
    ranking: (limit: number = 10) => api.get('/statistics/ranking', { params: { limit } }),
    distribution: () => api.get('/statistics/distribution'),
}

// 文件管理相关
export const fileApi = {
    list: (projectId: number, path?: string) =>
        api.get(`/files/project/${projectId}/list`, { params: { path } }),
    view: (projectId: number, path: string) =>
        api.get(`/files/project/${projectId}/view`, { params: { path } }),
    download: (projectId: number, path: string) =>
        api.get(`/files/project/${projectId}/download`, {
            params: { path },
            responseType: 'blob'
        }),
    uploadFile: (projectId: number, path: string, file: File) => {
        const formData = new FormData()
        formData.append('file', file)
        return api.post(`/files/project/${projectId}/upload-file?path=${encodeURIComponent(path)}`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        })
    },
    save: (projectId: number, path: string, content: string) =>
        api.put(`/files/project/${projectId}/save`, { content }, { params: { path } }),
    delete: (projectId: number, path: string) =>
        api.delete(`/files/project/${projectId}`, { params: { path } }),
    search: (projectId: number, keyword: string) =>
        api.get(`/files/project/${projectId}/search`, { params: { keyword } }),
}
