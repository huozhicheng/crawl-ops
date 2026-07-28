<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { NCard, NDataTable, NTag, NSpace, NInput, NDatePicker, NButton, useMessage } from 'naive-ui'
import { auditsApi } from '@/api'
import dayjs from 'dayjs'

const message = useMessage()
const loading = ref(false)
const items = ref<any[]>([])
const total = ref(0)
const pagination = ref({
    page: 1,
    pageSize: 20,
    showSizePicker: true,
    pageSizes: [10, 20, 50, 100],
    onChange: (page: number) => {
        pagination.value.page = page
        fetchList()
    },
    onUpdatePageSize: (pageSize: number) => {
        pagination.value.pageSize = pageSize
        pagination.value.page = 1
        fetchList()
    }
})

const filterForm = ref({
    username: '',
    action: '',
    dateRange: null as [number, number] | null
})

const columns = [
    { title: 'ID', key: 'id', width: 80 },
    { title: '时间', key: 'created_at', width: 180, render: (row: any) => dayjs(row.created_at).format('YYYY-MM-DD HH:mm:ss') },
    { title: '用户', key: 'username', width: 120 },
    { title: '动作', key: 'action', width: 150 },
    { title: '资源类型', key: 'resource_type', width: 100 },
    { title: '资源ID', key: 'resource_id', width: 80 },
    { title: '详情', key: 'detail', ellipsis: { tooltip: true } },
    { title: 'IP', key: 'ip', width: 120 },
]

const fetchList = async () => {
    loading.value = true
    try {
        const params: any = {
            page: pagination.value.page,
            page_size: pagination.value.pageSize,
            username: filterForm.value.username || undefined,
            action: filterForm.value.action || undefined,
        }
        if (filterForm.value.dateRange) {
            params.start_time = dayjs(filterForm.value.dateRange[0]).format('YYYY-MM-DD HH:mm:ss')
            params.end_time = dayjs(filterForm.value.dateRange[1]).format('YYYY-MM-DD HH:mm:ss')
        }

        const res: any = await auditsApi.list(params)
        items.value = res.items
        total.value = res.total
    } catch (error) {
        message.error('获取审计日志失败')
    } finally {
        loading.value = false
    }
}

const handleSearch = () => {
    pagination.value.page = 1
    fetchList()
}

const handleReset = () => {
    filterForm.value = { username: '', action: '', dateRange: null }
    handleSearch()
}

onMounted(fetchList)
</script>

<template>
    <n-card title="审计日志">
        <n-space style="margin-bottom: 16px">
            <n-input v-model:value="filterForm.username" placeholder="用户名" style="width: 150px" />
            <n-input v-model:value="filterForm.action" placeholder="动作" style="width: 150px" />
            <n-date-picker v-model:value="filterForm.dateRange" type="daterange" clearable />
            <n-button type="primary" @click="handleSearch">查询</n-button>
            <n-button @click="handleReset">重置</n-button>
        </n-space>

        <n-data-table
            remote
            :columns="columns"
            :data="items"
            :loading="loading"
            :pagination="pagination"
            :row-key="(row: any) => row.id"
        />
    </n-card>
</template>
