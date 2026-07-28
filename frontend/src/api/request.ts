import axios from 'axios'

const api = axios.create({
    baseURL: '/api/v1',
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
    },
})

// 是否正在刷新Token
let isRefreshing = false
let pendingRequests: Array<(token: string) => void> = []

// 请求拦截器
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token') || localStorage.getItem('token')
        if (token) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    (error) => {
        return Promise.reject(error)
    }
)

// 响应拦截器
api.interceptors.response.use(
    (response) => {
        return response.data
    },
    async (error) => {
        const originalRequest = error.config

        // 401错误且不是refresh请求
        if (error.response?.status === 401 && !originalRequest._retry) {
            if (isRefreshing) {
                // 等待刷新完成后重试
                return new Promise((resolve) => {
                    pendingRequests.push((token: string) => {
                        originalRequest.headers.Authorization = `Bearer ${token}`
                        resolve(api(originalRequest))
                    })
                })
            }

            originalRequest._retry = true
            isRefreshing = true

            const refreshToken = localStorage.getItem('refresh_token')
            if (refreshToken) {
                try {
                    const res = await axios.post('/api/v1/auth/refresh', {
                        refresh_token: refreshToken
                    })
                    const newToken = res.data.access_token
                    localStorage.setItem('access_token', newToken)
                    localStorage.setItem('token', newToken)

                    // 重试等待中的请求
                    pendingRequests.forEach((callback) => callback(newToken))
                    pendingRequests = []

                    originalRequest.headers.Authorization = `Bearer ${newToken}`
                    return api(originalRequest)
                } catch (refreshError) {
                    // 刷新失败，跳转登录
                    localStorage.removeItem('access_token')
                    localStorage.removeItem('refresh_token')
                    localStorage.removeItem('token')
                    window.location.href = '/login'
                    return Promise.reject(refreshError)
                } finally {
                    isRefreshing = false
                }
            } else {
                // 无refresh token，跳转登录
                localStorage.removeItem('token')
                window.location.href = '/login'
            }
        }

        return Promise.reject(error.response?.data || error)
    }
)

export default api
