<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { NCard, NDataTable, NButton, NSpace, NTag, NModal, NForm, NFormItem, NInput, NSelect, NSwitch, useMessage, useDialog } from 'naive-ui'
import api from '@/api/request'

const message = useMessage()
const loading = ref(false)
const showModal = ref(false)
const showTestModal = ref(false)
const configs = ref<any[]>([])
const isEdit = ref(false)
const editingId = ref<number | null>(null)

const formData = ref({
  name: '',
  type: 'feishu',
  webhook_url: '',
  secret: '',
  is_default: false,
})

const testData = ref({
  config_id: null as number | null,
  type: 'feishu',
  webhook_url: '',
  secret: '',
  title: '测试通知',
  content: '这是一条测试消息，如果您收到了，说明配置正确。',
})

const typeOptions = [
  { label: '飞书', value: 'feishu' },
  { label: '钉钉', value: 'dingtalk' },
  { label: '企业微信', value: 'wecom' },
]

const columns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '配置名称', key: 'name' },
  {
    title: '渠道类型',
    key: 'type',
    width: 100,
    render: (row: any) => {
      const labels: Record<string, string> = { feishu: '飞书', dingtalk: '钉钉', wecom: '企微' }
      return labels[row.type] || row.type
    }
  },
  {
    title: 'Webhook 地址',
    key: 'webhook_url',
    ellipsis: { tooltip: true }
  },
  {
    title: '状态',
    key: 'status',
    width: 80,
    render: (row: any) => h(NTag, {
      type: row.status === 1 ? 'success' : 'error'
    }, { default: () => row.status === 1 ? '启用' : '禁用' })
  },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    fixed: 'right' as const,
    render: (row: any) => h(NSpace, { wrap: false }, {
      default: () => [
        h(NButton, { size: 'small', onClick: () => handleEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', onClick: () => handleTest(row) }, { default: () => '测试' }),
        h(NButton, { size: 'small', type: 'error', onClick: () => handleDelete(row.id) }, { default: () => '删除' })
      ]
    })
  },
]

const fetchConfigs = async () => {
  loading.value = true
  try {
    const res: any = await api.get('/system/notifications')
    configs.value = res.items
  } catch (error) {
    message.error('获取配置失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  isEdit.value = false
  editingId.value = null
  formData.value = { name: '', type: 'feishu', webhook_url: '', secret: '', is_default: false }
  showModal.value = true
}

const openManualTest = () => {
  testData.value = {
    config_id: null,
    type: 'feishu',
    webhook_url: '',
    secret: '',
    title: '测试通知',
    content: '这是一条测试消息，如果您收到了，说明配置正确。',
  }
  showTestModal.value = true
}

const handleEdit = (row: any) => {
  isEdit.value = true
  editingId.value = row.id
  formData.value = {
    name: row.name,
    type: row.type,
    webhook_url: row.webhook_url,
    secret: '',
    is_default: row.is_default,
  }
  showModal.value = true
}

const handleSubmit = async () => {
  if (!formData.value.name || !formData.value.webhook_url) {
    message.warning('请填写完整信息')
    return
  }
  try {
    if (isEdit.value && editingId.value) {
      const payload: Record<string, unknown> = {
        name: formData.value.name,
        webhook_url: formData.value.webhook_url,
        is_default: formData.value.is_default,
      }
      if (formData.value.secret.trim()) {
        payload.secret = formData.value.secret
      }
      await api.put(`/system/notifications/${editingId.value}`, payload)
      message.success('更新成功')
    } else {
      await api.post('/system/notifications', formData.value)
      message.success('创建成功')
    }
    showModal.value = false
    fetchConfigs()
  } catch (error: any) {
    message.error(error.detail || (isEdit.value ? '更新失败' : '创建失败'))
  }
}

const dialog = useDialog()

const handleDelete = async (id: number) => {
  dialog.warning({
    title: '确认删除',
    content: '确定要删除该通知配置吗？',
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.delete(`/system/notifications/${id}`)
        message.success('删除成功')
        fetchConfigs()
      } catch (error) {
        message.error('删除失败')
      }
    }
  })
}

const handleTest = (row: any) => {
  testData.value = {
    config_id: row.id,
    type: row.type,
    webhook_url: row.webhook_url,
    secret: '',
    title: '测试通知',
    content: '这是一条测试消息，如果您收到了，说明配置正确。',
  }
  showTestModal.value = true
}

const handleTestSubmit = async () => {
  try {
    if (testData.value.config_id) {
      await api.post(`/system/notifications/${testData.value.config_id}/test`, {
        title: testData.value.title,
        content: testData.value.content,
      })
    } else {
      await api.post('/system/notifications/test', testData.value)
    }
    message.success('发送成功')
    showTestModal.value = false
  } catch (error: any) {
    message.error(error.detail || '发送失败')
  }
}

onMounted(fetchConfigs)
</script>

<template>
  <div >
    <n-card title="通知配置">
      <template #header-extra>
        <n-space>
          <n-button @click="openManualTest">发送测试通知</n-button>
          <n-button type="primary" @click="handleCreate">+ 添加配置</n-button>
        </n-space>
      </template>
      <n-data-table :columns="columns" :data="configs" :loading="loading" :bordered="false" />
    </n-card>

    <!-- 添加/编辑配置弹窗 -->
    <n-modal v-model:show="showModal" preset="dialog" :title="isEdit ? '编辑通知配置' : '添加通知配置'" style="width: 500px;">
      <n-form :model="formData" label-placement="left" label-width="100">
        <n-form-item label="配置名称">
          <n-input v-model:value="formData.name" placeholder="例如：研发群告警" />
        </n-form-item>
        <n-form-item label="渠道类型">
          <n-select v-model:value="formData.type" :options="typeOptions" :disabled="isEdit" />
        </n-form-item>
        <n-form-item label="Webhook 地址">
          <n-input v-model:value="formData.webhook_url" placeholder="https://..." />
        </n-form-item>
        <n-form-item label="签名密钥" v-if="formData.type === 'feishu' || formData.type === 'dingtalk'">
          <n-input v-model:value="formData.secret" type="password" show-password-on="mousedown" :placeholder="isEdit ? '留空以保留现有密钥' : '若配置了签名校验，请填写密钥'" />
        </n-form-item>
        <n-form-item label="设为默认">
          <n-switch v-model:value="formData.is_default" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-space>
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" @click="handleSubmit">确定</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 测试发送弹窗 -->
    <n-modal v-model:show="showTestModal" preset="dialog" title="发送测试通知" style="width: 500px;">
      <n-form :model="testData" label-placement="left" label-width="100">
        <n-form-item v-if="testData.config_id" label="发送方式">
          <span>使用已保存的 Webhook 地址和签名密钥</span>
        </n-form-item>
        <n-form-item v-if="!testData.config_id" label="渠道类型">
          <n-select v-model:value="testData.type" :options="typeOptions" />
        </n-form-item>
        <n-form-item v-if="!testData.config_id" label="Webhook 地址">
          <n-input v-model:value="testData.webhook_url" placeholder="https://..." />
        </n-form-item>
        <n-form-item v-if="!testData.config_id && (testData.type === 'feishu' || testData.type === 'dingtalk')" label="签名密钥">
          <n-input v-model:value="testData.secret" type="password" show-password-on="mousedown" placeholder="选填，用于签名校验" />
        </n-form-item>
        <n-form-item label="通知标题">
          <n-input v-model:value="testData.title" />
        </n-form-item>
        <n-form-item label="通知内容">
          <n-input v-model:value="testData.content" type="textarea" :rows="3" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-space>
          <n-button @click="showTestModal = false">取消</n-button>
          <n-button type="primary" @click="handleTestSubmit">发送测试</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>
