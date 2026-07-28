<script setup lang="ts">
import { computed, ref, onMounted, h } from 'vue'
import { NCard, NDataTable, NButton, NSpace, NInput, NModal, NForm, NFormItem, NSelect, NUpload, NUploadDragger, useMessage, useDialog } from 'naive-ui'
import type { UploadCustomRequestOptions } from 'naive-ui'
import api from '@/api/request'
import { projectApi } from '@/api'
import FileExplorer from '@/components/FileExplorer.vue'

const message = useMessage()
const loading = ref(false)
const showModal = ref(false)
const projects = ref<any[]>([])
const pagination = ref({ page: 1, pageSize: 20, itemCount: 0 })

const formData = ref({
  name: '',
  code: '',
  description: '',
  type: 'python',
  source_type: 'git',
  git_url: '',
  git_branch: 'main',
  entry_file: 'main.py',
  python_version: '3.10',
})

const showUploadModal = ref(false)
const currentUploadProjectId = ref<number | null>(null)
const dialogTitle = computed(() => (formData.value as any).id ? '编辑项目' : '新建项目')

// 文件浏览器
const showFileExplorer = ref(false)
const currentProject = ref<any>(null)

const columns = [
  { title: 'ID', key: 'id', width: 80 },
  {
    title: '项目名称',
    key: 'name',
    render: (row: any) => h('span', {
      style: { cursor: 'pointer', color: '#1890ff', fontWeight: '500' },
      onClick: () => handleViewFiles(row)
    }, row.name)
  },
  { title: '项目标识', key: 'code' },
  { title: '类型', key: 'type' },
  { title: '状态', key: 'status', render: (row: any) => row.status === 1 ? '正常' : '禁用' },
  {
    title: '操作',
    key: 'actions',
    width: 210,
    fixed: 'right' as const,
    render: (row: any) => h(NSpace, { wrap: false }, {
      default: () => {
        const actions = [
          h(NButton, { size: 'small', onClick: () => handleEdit(row) }, { default: () => '编辑' }),
          h(NButton, { size: 'small', type: 'error', onClick: () => handleDelete(row.id) }, { default: () => '删除' })
        ]

        if (row.source_type === 'git') {
          actions.unshift(
             h(NButton, { size: 'small', type: 'info', onClick: () => handleSync(row) }, { default: () => '同步' })
          )
        } else if (row.source_type === 'upload') {
          actions.unshift(
             h(NButton, { size: 'small', type: 'warning', onClick: () => handleUpload(row) }, { default: () => '上传' })
          )
        }
        return actions
      }
    })
  },
]

const typeOptions = [
  { label: 'Python', value: 'python' },
  { label: 'Scrapy', value: 'scrapy' },
]

const fetchProjects = async () => {
  loading.value = true
  try {
    const res: any = await projectApi.list({
      page: pagination.value.page,
      page_size: pagination.value.pageSize
    })
    projects.value = res.items
    pagination.value.itemCount = res.total
  } catch (error) {
    message.error('获取项目列表失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  formData.value = {
    name: '',
    code: '',
    description: '',
    type: 'python',
    source_type: 'git',
    git_url: '',
    git_branch: 'main',
    entry_file: 'main.py',
    python_version: '3.10',
  }
  showModal.value = true
}

const handleEdit = (row: any) => {
  formData.value = { ...row }
  showModal.value = true
}

const handleSubmit = async () => {
  try {
    if ((formData.value as any).id) {
      await projectApi.update((formData.value as any).id, formData.value)
      message.success('更新成功')
    } else {
      await projectApi.create(formData.value)
      message.success('创建成功')
    }
    showModal.value = false
    fetchProjects()
  } catch (error: any) {
    message.error(error.detail || '操作失败')
  }
}

const handleSync = async (row: any) => {
  try {
    message.loading('正在同步代码...')
    await api.post(`/projects/${row.id}/sync`)
    message.success('同步成功')
  } catch (error) {
    message.error('同步失败')
  }
}

const handleUpload = (row: any) => {
  currentUploadProjectId.value = row.id
  showUploadModal.value = true
}

const customRequest = async ({ file, onFinish, onError }: UploadCustomRequestOptions) => {
  const formData = new FormData()
  formData.append('file', file.file as File)

  try {
    await api.post(`/files/upload/project/${currentUploadProjectId.value}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    message.success('上传成功')
    onFinish()
    showUploadModal.value = false
  } catch (error) {
    message.error('上传失败')
    onError()
  }
}

const dialog = useDialog()

const handleDelete = async (id: number) => {
  dialog.warning({
    title: '确认删除',
    content: '删除项目后，其下的所有任务也会被删除。确定继续吗？',
    positiveText: '删除项目',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await projectApi.delete(id)
        message.success('删除成功')
        fetchProjects()
      } catch (error) {
        message.error('删除失败')
      }
    }
  })
}

const handleViewFiles = (row: any) => {
  currentProject.value = row
  showFileExplorer.value = true
}

onMounted(fetchProjects)
</script>

<template>
  <div >
    <n-card title="项目管理">
      <template #header-extra>
        <n-space>
          <n-input placeholder="按名称或标识搜索" style="width: 200px;" />
          <n-button type="primary" @click="handleCreate">+ 新建项目</n-button>
        </n-space>
      </template>
      <n-data-table
        :columns="columns"
        :data="projects"
        :loading="loading"
        :bordered="false"
      />
    </n-card>

    <n-modal v-model:show="showModal" preset="dialog" :title="dialogTitle" style="width: 500px;">
      <n-form :model="formData" label-placement="left" label-width="100">
        <n-form-item label="项目名称">
          <n-input v-model:value="formData.name" placeholder="请输入项目名称" />
        </n-form-item>
        <n-form-item label="项目标识">
          <n-input v-model:value="formData.code" placeholder="用于目录与任务引用，必须唯一" />
        </n-form-item>
        <n-form-item label="项目类型">
          <n-select v-model:value="formData.type" :options="typeOptions" />
        </n-form-item>
        <n-form-item label="入口文件">
          <n-input v-model:value="formData.entry_file" placeholder="main.py" />
        </n-form-item>
        <n-form-item label="描述">
          <n-input v-model:value="formData.description" type="textarea" placeholder="项目描述" />
        </n-form-item>
        <n-form-item label="代码来源">
          <n-select v-model:value="formData.source_type" :options="[{label: '本地上传', value: 'upload'}, {label: 'Git仓库', value: 'git'}]" />
        </n-form-item>
        <n-form-item label="Git 地址" v-if="formData.source_type === 'git'">
          <n-input v-model:value="formData.git_url" placeholder="https://github.com/username/repo.git" />
        </n-form-item>
        <n-form-item label="Git 分支" v-if="formData.source_type === 'git'">
          <n-input v-model:value="formData.git_branch" placeholder="main" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-space>
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" @click="handleSubmit">确定</n-button>
        </n-space>
      </template>
    </n-modal>

    <n-modal v-model:show="showUploadModal" preset="dialog" title="上传代码包" style="width: 400px;">
      <n-upload
        directory-dnd
        :custom-request="customRequest"
        accept=".zip"
      >
        <n-upload-dragger>
          <div style="margin-bottom: 12px">
            点击或将文件拖到此处上传
          </div>
          <div style="color: #86909C">
            仅支持 .zip 压缩包；上传后会自动解压到项目目录
          </div>
        </n-upload-dragger>
      </n-upload>
    </n-modal>

    <!-- 文件浏览器 -->
    <FileExplorer
      v-model:show="showFileExplorer"
      :project-id="currentProject?.id || 0"
      :project-name="currentProject?.name || ''"
    />
  </div>
</template>
