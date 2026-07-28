<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { NCard, NDataTable, NButton, NSpace, NTag, NModal, NForm, NFormItem, NInput, NSelect, NInputNumber, NSwitch, useMessage, useDialog } from 'naive-ui'
import { taskApi, projectApi, venvsApi } from '@/api'

const message = useMessage()
const loading = ref(false)
const showModal = ref(false)
const tasks = ref<any[]>([])
const projects = ref<any[]>([])
const venvs = ref<any[]>([])

const formData = ref({
  name: '',
  project_id: null as number | null,
  venv_id: null as number | null,
  schedule_type: 'cron',
  cron_expression: '0 8 * * *',
  interval_seconds: 3600,
  random_start_hour: 8,
  random_end_hour: 10,
  command: 'python main.py',
  timeout_seconds: 3600,
  retry_count: 0,
  retry_interval: 60,
  use_proxy: 0,
})

const columns = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '任务名称', key: 'name' },
  { title: '调度类型', key: 'schedule_type' },
  {
    title: 'Cron/间隔',
    key: 'cron_expression',
    render: (row: any) => {
        if (row.schedule_type === 'cron') return row.cron_expression
        if (row.schedule_type === 'interval') return `${row.interval_seconds}秒`
        if (row.schedule_type === 'random') return `每日 ${row.random_start_hour}:00–${row.random_end_hour}:00 随机执行`
        return '-'
    }
  },
  {
    title: '下次运行',
    key: 'scheduled_time',
    render: (row: any) => {
      if (!row.scheduled_time) return '-'
      if (row.schedule_type === 'once' && row.status !== 1) return '-'
      return new Date(row.scheduled_time).toLocaleString('zh-CN', { hour12: false })
    }
  },
  {
    title: '状态',
    key: 'status',
    render: (row: any) => h(NTag, { type: row.status === 1 ? 'success' : 'error' }, { default: () => row.status === 1 ? '启用' : '禁用' })
  },
  {
    title: '操作',
    key: 'actions',
    width: 240,
    fixed: 'right' as const,
    render: (row: any) => h(NSpace, { wrap: false }, {
      default: () => [
        h(NButton, { size: 'small', type: 'primary', onClick: () => handleRun(row.id) }, { default: () => '▶ 执行' }),
        h(NButton, { size: 'small', onClick: () => handleEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', type: 'error', onClick: () => handleDelete(row.id) }, { default: () => '删除' })
      ]
    })
  },
]

const scheduleOptions = [
  { label: 'Cron 定时', value: 'cron' },
  { label: '固定间隔', value: 'interval' },
  { label: '随机时段', value: 'random' },
  { label: '单次执行', value: 'once' },
]

const fetchTasks = async () => {
  loading.value = true
  try {
    const res: any = await taskApi.list()
    tasks.value = res.items
  } catch (error) {
    message.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

const fetchProjects = async () => {
  const res: any = await projectApi.list({ page_size: 100 })
  projects.value = res.items.map((p: any) => ({ label: p.name, value: p.id }))
}

const fetchVenvs = async () => {
    const res: any = await venvsApi.list({ page_size: 100 })
    venvs.value = res.items.map((v: any) => ({ label: `${v.name} (${v.python_version})`, value: v.id }))
}

const handleCreate = () => {
  formData.value = {
    name: '',
    project_id: null,
    schedule_type: 'cron',
    cron_expression: '0 8 * * *',
    interval_seconds: 3600,
    random_start_hour: 8,
    random_end_hour: 10,
    command: 'python main.py',
    timeout_seconds: 3600,
    retry_count: 0,
    retry_interval: 60,
    use_proxy: 0,
    venv_id: null,
  }
  showModal.value = true
}

const handleEdit = (row: any) => {
  formData.value = { ...row }
  showModal.value = true
}

const handleSubmit = async () => {
  if (!formData.value.project_id) {
    message.warning('请选择项目')
    return
  }
  try {
    if ((formData.value as any).id) {
      await taskApi.update((formData.value as any).id, formData.value)
      message.success('更新成功')
    } else {
      await taskApi.create(formData.value)
      message.success('创建成功')
    }
    showModal.value = false
    fetchTasks()
  } catch (error: any) {
    message.error(error.detail || '操作失败')
  }
}

const dialog = useDialog()

const handleDelete = async (id: number) => {
  dialog.warning({
    title: '确认删除',
    content: '确定要删除该任务吗？此操作不可恢复。',
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await taskApi.delete(id)
        message.success('删除成功')
        fetchTasks()
      } catch (error) {
        message.error('删除失败')
      }
    }
  })
}

const handleRun = async (id: number) => {
  try {
    await taskApi.run(id)
    message.success('任务已加入执行队列')
  } catch (error) {
    message.error('执行失败')
  }
}

onMounted(() => {
  fetchTasks()
  fetchProjects()
  fetchVenvs()
})
</script>

<template>
  <div >
    <n-card title="任务管理">
      <template #header-extra>
        <n-button type="primary" @click="handleCreate">+ 新建任务</n-button>
      </template>
      <n-data-table
        :columns="columns"
        :data="tasks"
        :loading="loading"
        :bordered="false"
      />
    </n-card>

    <n-modal v-model:show="showModal" preset="dialog" title="任务信息" style="width: 550px;">
      <n-form :model="formData" label-placement="left" label-width="100">
        <n-form-item label="任务名称">
          <n-input v-model:value="formData.name" placeholder="请输入任务名称" />
        </n-form-item>
        <n-form-item label="所属项目">
          <n-select v-model:value="formData.project_id" :options="projects" placeholder="选择项目" />
        </n-form-item>
        <n-form-item label="运行环境">
          <n-select v-model:value="formData.venv_id" :options="venvs" placeholder="使用系统 Python" clearable />
        </n-form-item>
        <n-form-item label="调度类型">
          <n-select v-model:value="formData.schedule_type" :options="scheduleOptions" />
        </n-form-item>
        <n-form-item v-if="formData.schedule_type === 'cron'" label="Cron表达式">
          <n-input v-model:value="formData.cron_expression" placeholder="0 8 * * *" />
        </n-form-item>
        <n-form-item v-if="formData.schedule_type === 'interval'" label="间隔(秒)">
          <n-input-number v-model:value="formData.interval_seconds" :min="60" />
        </n-form-item>
        <n-form-item v-if="formData.schedule_type === 'random'" label="随机执行时段">
          <n-space>
            <n-input-number v-model:value="formData.random_start_hour" :min="0" :max="22" style="width: 100px" />
            <span>:00 至</span>
            <n-input-number v-model:value="formData.random_end_hour" :min="(formData.random_start_hour ?? 0) + 1" :max="23" style="width: 100px" />
            <span>:00</span>
          </n-space>
        </n-form-item>
        <n-form-item label="执行命令">
          <n-input v-model:value="formData.command" placeholder="python main.py" />
        </n-form-item>
        <n-form-item label="超时(秒)">
          <n-input-number v-model:value="formData.timeout_seconds" :min="60" />
        </n-form-item>
        <n-form-item label="失败重试">
          <n-space>
            <n-input-number v-model:value="formData.retry_count" :min="0" :max="10" style="width: 100px" />
            <span>次，间隔</span>
            <n-input-number v-model:value="formData.retry_interval" :min="10" :disabled="formData.retry_count === 0" style="width: 100px" />
            <span>秒</span>
          </n-space>
        </n-form-item>
        <n-form-item label="使用代理">
          <n-switch v-model:value="formData.use_proxy" :checked-value="1" :unchecked-value="0" />
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
