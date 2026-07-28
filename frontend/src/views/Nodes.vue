<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { NCard, NDataTable, NButton, NSpace, NTag, NModal, NForm, NFormItem, NInput, NInputNumber, NStatistic, NGrid, NGridItem, useMessage, useDialog } from 'naive-ui'
import { nodeApi } from '@/api'
import dayjs from 'dayjs'

const message = useMessage()
const loading = ref(false)
const showModal = ref(false)
const nodes = ref<any[]>([])
const stats = ref({ total: 0, online: 0 })

const formData = ref({
  name: '',
  host: '',
  port: 8080,
})

const columns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '节点名称', key: 'name' },
  { title: '主机地址', key: 'host' },
  { title: '端口', key: 'port', width: 80, render: (row: any) => row.port > 0 ? row.port : '-' },
  { title: '操作系统', key: 'os_type', width: 100 },
  {
    title: '状态',
    key: 'status',
    width: 80,
    render: (row: any) => h(NTag, {
      type: row.status === 'online' ? 'success' : 'error'
    }, { default: () => row.status === 'online' ? '在线' : '离线' })
  },
  { title: 'CPU', key: 'cpu_usage', width: 80, render: (row: any) => row.cpu_usage ? `${row.cpu_usage}%` : '-' },
  { title: '内存', key: 'memory_usage', width: 80, render: (row: any) => row.memory_usage ? `${row.memory_usage}%` : '-' },
  { title: '磁盘', key: 'disk_usage', width: 80, render: (row: any) => row.disk_usage ? `${row.disk_usage}%` : '-' },
  {
    title: '最后心跳',
    key: 'last_heartbeat',
    width: 160,
    render: (row: any) => row.last_heartbeat ? dayjs(row.last_heartbeat).format('YYYY-MM-DD HH:mm:ss') : '-'
  },
  {
    title: '操作',
    key: 'actions',
    width: 140,
    fixed: 'right' as const,
    render: (row: any) => h(NSpace, { wrap: false }, {
      default: () => {
        const buttons = [
          h(NButton, {
            size: 'small',
            type: 'primary',
            onClick: () => handlePing(row.id)
          }, { default: () => '检查' })
        ]
        if (row.status !== 'online') {
          buttons.push(
            h(NButton, {
              size: 'small',
              type: 'error',
              onClick: () => handleDelete(row.id)
            }, { default: () => '删除' })
          )
        }
        return buttons
      }
    })
  },
]

const fetchNodes = async () => {
  loading.value = true
  try {
    const res: any = await nodeApi.list()
    nodes.value = res.items
    stats.value.total = res.total
    stats.value.online = res.items.filter((n: any) => n.status === 'online').length
  } catch (error) {
    message.error('获取节点列表失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  formData.value = { name: '', host: '', port: 8080 }
  showModal.value = true
}

const handleSubmit = async () => {
  if (!formData.value.name || !formData.value.host) {
    message.warning('请填写完整信息')
    return
  }
  try {
    const res: any = await nodeApi.create(formData.value)
    message.success(`节点已添加，访问令牌：${res.token}`)
    showModal.value = false
    fetchNodes()
  } catch (error: any) {
    message.error(error.detail || '添加失败')
  }
}

const dialog = useDialog()

const handleDelete = async (id: number) => {
  dialog.warning({
    title: '确认删除',
    content: '确定要删除该节点吗？',
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await nodeApi.delete(id)
        message.success('删除成功')
        fetchNodes()
      } catch (error) {
        message.error('删除失败')
      }
    }
  })
}

const handlePing = async (id: number) => {
  try {
    const res: any = await nodeApi.ping(id)
    message.success(`节点状态：${res.status}`)
  } catch (error) {
    message.error('连通性检查失败')
  }
}

onMounted(fetchNodes)
</script>

<template>
  <div >
    <n-grid :cols="2" :x-gap="16" style="margin-bottom: 16px;">
      <n-grid-item>
        <n-card><n-statistic label="总节点数" :value="stats.total" /></n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card><n-statistic label="在线节点" :value="stats.online" /></n-card>
      </n-grid-item>
    </n-grid>

    <n-card title="节点管理">
      <template #header-extra>
        <n-button type="primary" @click="handleCreate">+ 添加节点</n-button>
      </template>
      <n-data-table :columns="columns" :data="nodes" :loading="loading" :bordered="false" />
    </n-card>

    <n-modal v-model:show="showModal" preset="dialog" title="添加节点" style="width: 400px;">
      <n-form :model="formData" label-placement="left" label-width="80">
        <n-form-item label="节点名称">
          <n-input v-model:value="formData.name" placeholder="例如：node-1" />
        </n-form-item>
        <n-form-item label="主机地址">
          <n-input v-model:value="formData.host" placeholder="192.168.1.100" />
        </n-form-item>
        <n-form-item label="端口">
          <n-input-number v-model:value="formData.port" :min="1" :max="65535" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-space>
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" @click="handleSubmit">确定</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>
