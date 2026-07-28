<script setup lang="ts">
import { ref, computed, h, watch, onMounted } from 'vue'
import {
  NModal, NCard, NDataTable, NButton, NSpace, NInput, NBreadcrumb,
  NBreadcrumbItem, NUpload, useMessage, NIcon, NPopconfirm,
  NTag, NCode, NSpin, NEmpty, NInputGroup
} from 'naive-ui'
import {
  FolderOutlined, FileOutlined, DownloadOutlined, DeleteOutlined,
  EditOutlined, SearchOutlined, UploadOutlined, ReloadOutlined,
  EyeOutlined, SaveOutlined, CloseOutlined
} from '@vicons/antd'
import type { UploadCustomRequestOptions } from 'naive-ui'
import { fileApi } from '@/api'

interface FileItem {
  name: string
  type: 'file' | 'directory'
  size: number
  modified: string
  path: string
}

const props = defineProps<{
  show: boolean
  projectId: number
  projectName: string
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
}>()

const message = useMessage()

const loading = ref(false)
const files = ref<FileItem[]>([])
const currentPath = ref('')
const searchKeyword = ref('')
const searchResults = ref<FileItem[]>([])
const searching = ref(false)

// 文件预览/编辑
const showPreview = ref(false)
const previewContent = ref('')
const previewFilename = ref('')
const previewPath = ref('')
const isEditing = ref(false)
const editContent = ref('')

// 计算面包屑路径
const pathParts = computed(() => {
  if (!currentPath.value) return []
  return currentPath.value.split('/').filter(p => p)
})

// 格式化文件大小
const formatSize = (bytes: number) => {
  if (bytes === 0) return '-'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// 格式化时间
const formatTime = (isoString: string) => {
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 获取文件图标
const getFileIcon = (item: FileItem) => {
  return item.type === 'directory' ? FolderOutlined : FileOutlined
}

// 获取文件扩展名
const getFileExtension = (filename: string) => {
  const parts = filename.split('.')
  return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : ''
}

// 判断是否可预览
const isPreviewable = (filename: string) => {
  const ext = getFileExtension(filename)
  const previewableExts = ['txt', 'py', 'js', 'ts', 'vue', 'json', 'xml', 'html', 'css', 'md', 'yaml', 'yml', 'ini', 'conf', 'sh', 'bat']
  return previewableExts.includes(ext)
}

// 表格列定义
const columns = [
  {
    title: '文件名',
    key: 'name',
    render: (row: FileItem) => h(NSpace, { align: 'center' }, {
      default: () => [
        h(NIcon, { size: 20, color: row.type === 'directory' ? '#f59e0b' : '#6b7280' }, {
          default: () => h(getFileIcon(row))
        }),
        h('span', {
          style: {
            cursor: 'pointer',
            color: row.type === 'directory' ? '#1890ff' : 'inherit',
            fontWeight: row.type === 'directory' ? '500' : 'normal'
          },
          onClick: () => handleItemClick(row)
        }, row.name)
      ]
    })
  },
  {
    title: '类型',
    key: 'type',
    width: 100,
    render: (row: FileItem) => h(NTag, {
      size: 'small',
      type: row.type === 'directory' ? 'warning' : 'default'
    }, {
      default: () => row.type === 'directory' ? '文件夹' : '文件'
    })
  },
  {
    title: '大小',
    key: 'size',
    width: 100,
    render: (row: FileItem) => formatSize(row.size)
  },
  {
    title: '修改时间',
    key: 'modified',
    width: 150,
    render: (row: FileItem) => formatTime(row.modified)
  },
  {
    title: '操作',
    key: 'actions',
    width: 260,
    fixed: 'right' as const,
    render: (row: FileItem) => h(NSpace, { size: 'small' }, {
      default: () => {
        const actions = []

        if (row.type === 'file') {
          // 预览按钮
          if (isPreviewable(row.name)) {
            actions.push(
              h(NButton, {
                size: 'small',
                type: 'info',
                onClick: () => handlePreview(row)
              }, {
                default: () => '预览',
                icon: () => h(NIcon, null, { default: () => h(EyeOutlined) })
              })
            )
          }

          // 下载按钮
          actions.push(
            h(NButton, {
              size: 'small',
              onClick: () => handleDownload(row)
            }, {
              default: () => '下载',
              icon: () => h(NIcon, null, { default: () => h(DownloadOutlined) })
            })
          )
        }

        // 删除按钮
        actions.push(
          h(NPopconfirm, {
            onPositiveClick: () => handleDelete(row)
          }, {
            default: () => `确定删除 ${row.name} 吗？`,
            trigger: () => h(NButton, {
              size: 'small',
              type: 'error'
            }, {
              default: () => '删除',
              icon: () => h(NIcon, null, { default: () => h(DeleteOutlined) })
            })
          })
        )

        return actions
      }
    })
  }
]

// 加载文件列表
const loadFiles = async (path: string = '') => {
  loading.value = true
  try {
    const res: any = await fileApi.list(props.projectId, path)
    files.value = res.files
    currentPath.value = path
  } catch (error: any) {
    message.error(error.detail || '加载文件列表失败')
  } finally {
    loading.value = false
  }
}

// 点击文件/文件夹
const handleItemClick = (item: FileItem) => {
  if (item.type === 'directory') {
    loadFiles(item.path)
  } else if (isPreviewable(item.name)) {
    handlePreview(item)
  }
}

// 导航到指定路径
const navigateTo = (index: number) => {
  if (index === -1) {
    loadFiles('')
  } else {
    const path = pathParts.value.slice(0, index + 1).join('/')
    loadFiles(path)
  }
}

// 返回上级目录
const goBack = () => {
  const parts = currentPath.value.split('/').filter(p => p)
  if (parts.length > 0) {
    parts.pop()
    loadFiles(parts.join('/'))
  }
}

// 预览文件
const handlePreview = async (item: FileItem) => {
  loading.value = true
  try {
    const res: any = await fileApi.view(props.projectId, item.path)
    previewContent.value = res.content
    previewFilename.value = res.filename
    previewPath.value = item.path
    showPreview.value = true
    isEditing.value = false
  } catch (error: any) {
    message.error(error.detail || '预览失败')
  } finally {
    loading.value = false
  }
}

// 开始编辑
const startEdit = () => {
  editContent.value = previewContent.value
  isEditing.value = true
}

// 保存编辑
const saveEdit = async () => {
  loading.value = true
  try {
    await fileApi.save(props.projectId, previewPath.value, editContent.value)
    message.success('保存成功')
    previewContent.value = editContent.value
    isEditing.value = false
    loadFiles(currentPath.value) // 刷新列表
  } catch (error: any) {
    message.error(error.detail || '保存失败')
  } finally {
    loading.value = false
  }
}

// 取消编辑
const cancelEdit = () => {
  isEditing.value = false
  editContent.value = ''
}

// 下载文件
const handleDownload = async (item: FileItem) => {
  try {
    const res: any = await fileApi.download(props.projectId, item.path)
    const url = window.URL.createObjectURL(new Blob([res]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', item.name)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success('下载成功')
  } catch (error: any) {
    message.error('下载失败')
  }
}

// 删除文件
const handleDelete = async (item: FileItem) => {
  try {
    await fileApi.delete(props.projectId, item.path)
    message.success('删除成功')
    loadFiles(currentPath.value)
  } catch (error: any) {
    message.error(error.detail || '删除失败')
  }
}

// 上传文件
const customRequest = async ({ file, onFinish, onError }: UploadCustomRequestOptions) => {
  try {
    await fileApi.uploadFile(props.projectId, currentPath.value, file.file as File)
    message.success('上传成功')
    onFinish()
    loadFiles(currentPath.value)
  } catch (error: any) {
    message.error(error.detail || '上传失败')
    onError()
  }
}

// 搜索文件
const handleSearch = async () => {
  if (!searchKeyword.value.trim()) {
    message.warning('请输入搜索关键词')
    return
  }

  searching.value = true
  try {
    const res: any = await fileApi.search(props.projectId, searchKeyword.value)
    searchResults.value = res.results
    message.success(`找到 ${res.count} 个文件`)
  } catch (error: any) {
    message.error(error.detail || '搜索失败')
  } finally {
    searching.value = false
  }
}

// 清除搜索
const clearSearch = () => {
  searchKeyword.value = ''
  searchResults.value = []
}

// 从搜索结果打开文件
const openSearchResult = (item: FileItem) => {
  const dirPath = item.path.substring(0, item.path.lastIndexOf('/'))
  loadFiles(dirPath)
  clearSearch()
}

// 监听显示状态
watch(() => props.show, (newVal) => {
  if (newVal) {
    loadFiles('')
    clearSearch()
  }
})

onMounted(() => {
  if (props.show) {
    loadFiles('')
  }
})
</script>

<template>
  <n-modal
    :show="show"
    @update:show="emit('update:show', $event)"
    preset="card"
    :title="`项目文件浏览 - ${projectName}`"
    style="width: 80%; max-width: 900px;"
    :segmented="{ content: 'soft' }"
  >
    <n-space vertical :size="16">
      <!-- 工具栏 -->
      <n-space justify="space-between">
        <n-space>
          <!-- 面包屑导航 -->
          <n-breadcrumb>
            <n-breadcrumb-item @click="navigateTo(-1)" style="cursor: pointer;">
              根目录
            </n-breadcrumb-item>
            <n-breadcrumb-item
              v-for="(part, index) in pathParts"
              :key="index"
              @click="navigateTo(index)"
              style="cursor: pointer;"
            >
              {{ part }}
            </n-breadcrumb-item>
          </n-breadcrumb>
        </n-space>

        <n-space>
          <!-- 搜索 -->
          <n-input-group>
            <n-input
              v-model:value="searchKeyword"
              placeholder="搜索文件名..."
              style="width: 200px;"
              @keyup.enter="handleSearch"
              clearable
            />
            <n-button type="primary" @click="handleSearch" :loading="searching">
              <template #icon>
                <n-icon><SearchOutlined /></n-icon>
              </template>
            </n-button>
          </n-input-group>

          <!-- 上传文件 -->
          <n-upload
            :custom-request="customRequest"
            :show-file-list="false"
          >
            <n-button>
              <template #icon>
                <n-icon><UploadOutlined /></n-icon>
              </template>
              上传文件
            </n-button>
          </n-upload>

          <!-- 刷新 -->
          <n-button @click="loadFiles(currentPath)">
            <template #icon>
              <n-icon><ReloadOutlined /></n-icon>
            </template>
            刷新
          </n-button>

          <!-- 返回上级 -->
          <n-button @click="goBack" :disabled="!currentPath">
            返回上级
          </n-button>
        </n-space>
      </n-space>

      <!-- 搜索结果 -->
      <n-card v-if="searchResults.length > 0" title="搜索结果" size="small">
        <template #header-extra>
          <n-button text @click="clearSearch">清除</n-button>
        </template>
        <n-space vertical>
          <div
            v-for="item in searchResults"
            :key="item.path"
            style="cursor: pointer; padding: 8px; border-radius: 4px;"
            :style="{ backgroundColor: 'var(--n-color-hover)' }"
            @click="openSearchResult(item)"
          >
            <n-space align="center">
              <n-icon :component="FileOutlined" />
              <span>{{ item.path }}</span>
              <n-tag size="small">{{ formatSize(item.size) }}</n-tag>
            </n-space>
          </div>
        </n-space>
      </n-card>

      <!-- 文件列表 -->
      <n-spin :show="loading">
        <transition name="fade" mode="out-in">
          <n-data-table
            :key="currentPath"
            :columns="columns"
            :data="files"
            :bordered="false"
            :single-line="false"
            size="small"
            :max-height="500"
            :min-height="300"
          >
            <template #empty>
              <n-empty description="暂无文件" />
            </template>
          </n-data-table>
        </transition>
      </n-spin>
    </n-space>
  </n-modal>

  <!-- 文件预览/编辑弹窗 -->
  <n-modal
    v-model:show="showPreview"
    preset="card"
    :title="isEditing ? `编辑 - ${previewFilename}` : `预览 - ${previewFilename}`"
    style="width: 90%; max-width: 1000px;"
  >
    <template #header-extra>
      <n-space>
        <n-button v-if="!isEditing" @click="startEdit">
          <template #icon>
            <n-icon><EditOutlined /></n-icon>
          </template>
          编辑
        </n-button>
        <n-button v-if="isEditing" type="primary" @click="saveEdit" :loading="loading">
          <template #icon>
            <n-icon><SaveOutlined /></n-icon>
          </template>
          保存
        </n-button>
        <n-button v-if="isEditing" @click="cancelEdit">
          <template #icon>
            <n-icon><CloseOutlined /></n-icon>
          </template>
          取消
        </n-button>
      </n-space>
    </template>

    <div v-if="!isEditing">
      <n-code
        :code="previewContent"
        :language="getFileExtension(previewFilename)"
        show-line-numbers
        style="max-height: 600px; overflow: auto;"
      />
    </div>

    <div v-else>
      <n-input
        v-model:value="editContent"
        type="textarea"
        :rows="25"
        placeholder="编辑文件内容..."
        style="font-family: 'Consolas', 'Monaco', monospace;"
      />
    </div>
  </n-modal>
</template>

<style scoped>
:deep(.n-data-table-td) {
  padding: 8px 12px !important;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
