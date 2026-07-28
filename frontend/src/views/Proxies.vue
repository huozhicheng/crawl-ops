<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { NCard, NDataTable, NButton, NSpace, NTag, NModal, NForm, NFormItem, NInput, NInputNumber, NStatistic, NGrid, NGridItem, useMessage, useDialog } from 'naive-ui'
import { proxyApi } from '@/api'

const message = useMessage()
const loading = ref(false)
const showModal = ref(false)
const showImportModal = ref(false)
const proxies = ref<any[]>([])
const stats = ref({ total: 0, available: 0, avgScore: 0 })

const formData = ref({
  ip: '',
  port: 8080,
  protocol: 'http',
})

const importData = ref({
  proxies: '',
  protocol: 'http',
})

const columns = [
  { title: 'IP地址', key: 'ip' },
  { title: '端口', key: 'port', width: 80 },
  { title: '协议', key: 'protocol', width: 80 },
  { title: '评分', key: 'score', width: 80 },
  { title: '响应(ms)', key: 'response_time', width: 100 },
  {
    title: '状态',
    key: 'status',
    width: 80,
    render: (row: any) => h(NTag, { type: row.status === 1 ? 'success' : 'error' }, { default: () => row.status === 1 ? '可用' : '不可用' })
  },
  {
    title: '操作',
    key: 'actions',
    width: 140,
    fixed: 'right' as const,
    render: (row: any) => h(NSpace, { wrap: false }, {
      default: () => [
        h(NButton, {
          size: 'small',
          type: 'primary',
          onClick: () => handleVerify(row.id)
        }, { default: () => '检测' }),
        h(NButton, {
          size: 'small',
          type: 'error',
          onClick: () => handleDelete(row.id)
        }, { default: () => '删除' })
      ]
    })
  },
]

const fetchProxies = async () => {
  loading.value = true
  try {
    const res: any = await proxyApi.list()
    proxies.value = res.items
    stats.value.total = res.total
    stats.value.available = res.items.filter((p: any) => p.status === 1 && p.score >= 30).length
    stats.value.avgScore = res.items.length ? Math.round(res.items.reduce((sum: number, p: any) => sum + p.score, 0) / res.items.length) : 0
  } catch (error) {
    message.error('获取代理列表失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  formData.value = { ip: '', port: 8080, protocol: 'http' }
  showModal.value = true
}

const handleSubmit = async () => {
  try {
    await proxyApi.create(formData.value)
    message.success('添加成功')
    showModal.value = false
    fetchProxies()
  } catch (error: any) {
    message.error(error.detail || '添加失败')
  }
}

const dialog = useDialog()

const handleDelete = async (id: number) => {
  dialog.warning({
    title: '确认删除',
    content: '确定要删除该代理吗？',
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await proxyApi.delete(id)
        message.success('删除成功')
        fetchProxies()
      } catch (error) {
        message.error('删除失败')
      }
    }
  })
}

const handleVerify = async (id: number) => {
  try {
    const res: any = await proxyApi.verify(id)
    message.success(res.valid ? '代理可用' : '代理不可用')
    fetchProxies()
  } catch (error) {
    message.error('验证失败')
  }
}

const handleImport = async () => {
  const lines = importData.value.proxies.split('\n').filter(l => l.trim())
  if (lines.length === 0) {
    message.warning('请输入代理列表')
    return
  }
  try {
    const res: any = await proxyApi.import({
      proxies: lines,
      protocol: importData.value.protocol
    })
    message.success(`成功导入 ${res.count} 个代理`)
    showImportModal.value = false
    importData.value.proxies = ''
    fetchProxies()
  } catch (error) {
    message.error('导入失败')
  }
}

const handleVerifyAll = async () => {
  try {
    await proxyApi.verifyAll()
    message.success('验证任务已启动')
  } catch (error) {
    message.error('启动失败')
  }
}

onMounted(fetchProxies)
</script>

<template>
  <div >
    <n-grid :cols="3" :x-gap="16" style="margin-bottom: 16px;">
      <n-grid-item>
        <n-card><n-statistic label="总数" :value="stats.total" /></n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card><n-statistic label="可用" :value="stats.available" /></n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card><n-statistic label="平均评分" :value="stats.avgScore" /></n-card>
      </n-grid-item>
    </n-grid>

    <n-card title="代理池管理">
      <template #header-extra>
        <n-space>
          <n-button @click="handleVerifyAll">验证全部</n-button>
          <n-button @click="showImportModal = true">批量导入</n-button>
          <n-button type="primary" @click="handleCreate">+ 添加</n-button>
        </n-space>
      </template>
      <n-data-table :columns="columns" :data="proxies" :loading="loading" :bordered="false" />
    </n-card>

    <!-- 添加代理 -->
    <n-modal v-model:show="showModal" preset="dialog" title="添加代理" style="width: 400px;">
      <n-form :model="formData" label-placement="left" label-width="60">
        <n-form-item label="IP">
          <n-input v-model:value="formData.ip" placeholder="192.168.1.1" />
        </n-form-item>
        <n-form-item label="端口">
          <n-input-number v-model:value="formData.port" :min="1" :max="65535" />
        </n-form-item>
        <n-form-item label="协议">
          <n-input v-model:value="formData.protocol" placeholder="http/https/socks5" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-space>
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" @click="handleSubmit">确定</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 批量导入 -->
    <n-modal v-model:show="showImportModal" preset="dialog" title="批量导入代理" style="width: 500px;">
      <n-form :model="importData" label-placement="top">
        <n-form-item label="协议">
          <n-input v-model:value="importData.protocol" placeholder="http" />
        </n-form-item>
        <n-form-item label="代理列表（每行一个，格式：IP:端口）">
          <n-input
            v-model:value="importData.proxies"
            type="textarea"
            :rows="10"
            placeholder="192.168.1.1:8080&#10;192.168.1.2:8080"
          />
        </n-form-item>
      </n-form>
      <template #action>
        <n-space>
          <n-button @click="showImportModal = false">取消</n-button>
          <n-button type="primary" @click="handleImport">导入</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>
