import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api'

export const useAuthStore = defineStore('auth', () => {
    const accessToken = ref(localStorage.getItem('access_token') || '')
    const refreshToken = ref(localStorage.getItem('refresh_token') || '')
    const user = ref<any>(null)

    const login = async (username: string, password: string) => {
        const res: any = await authApi.login({ username, password })
        accessToken.value = res.access_token
        refreshToken.value = res.refresh_token
        localStorage.setItem('access_token', res.access_token)
        localStorage.setItem('refresh_token', res.refresh_token)
        localStorage.setItem('token', res.access_token) // 兼容旧代码
        return res
    }

    const refresh = async () => {
        if (!refreshToken.value) {
            throw new Error('No refresh token')
        }
        const res: any = await authApi.refresh({ refresh_token: refreshToken.value })
        accessToken.value = res.access_token
        localStorage.setItem('access_token', res.access_token)
        localStorage.setItem('token', res.access_token)
        return res
    }

    const logout = async () => {
        try {
            await authApi.logout()
        } finally {
            accessToken.value = ''
            refreshToken.value = ''
            user.value = null
            localStorage.removeItem('access_token')
            localStorage.removeItem('refresh_token')
            localStorage.removeItem('token')
        }
    }

    const isAuthenticated = () => !!accessToken.value

    return {
        accessToken,
        refreshToken,
        user,
        login,
        refresh,
        logout,
        isAuthenticated,
    }
})
