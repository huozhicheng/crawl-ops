<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed, h, nextTick } from 'vue'
import { NCard, NDataTable, NTag, NSelect, NSpace, NButton, NModal, NDatePicker, NPopconfirm, NProgress, NInput, NSwitch, NIcon, useMessage } from 'naive-ui'
import { SearchOutline, ArrowUpOutline, ArrowDownOutline } from '@vicons/ionicons5'
import dayjs from 'dayjs'
import api from '@/api/request'
import { taskApi } from '@/api'

const loading = ref(false)
const executions = ref<any[]>([])
const pagination = ref({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
})

const message = useMessage()

const statusOptions = [
  { label: '全部状态', value: '' },
  { label: '待执行', value: 'pending' },
  { label: '执行中', value: 'running' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '超时', value: 'timeout' },
  { label: '已停止', value: 'stopped' },
]

const taskOptions = ref<{ label: string; value: number | string }[]>([
  { label: '全部任务', value: '' }
])

const selectedStatus = ref('')
const selectedTaskId = ref<number | string>('')
const dateRange = ref<[number, number] | null>(null)

const columns = [
  { title: 'ID', key: 'id', width: 60, fixed: 'left' as const },
  { title: '任务名称', key: 'task_name', width: 150, ellipsis: { tooltip: true } },
  { title: '任务ID', key: 'task_id', width: 60 },
  { title: '触发方式', key: 'trigger_type', width: 100 },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row: any) => {
      const typeMap: Record<string, 'default' | 'error' | 'primary' | 'info' | 'success' | 'warning'> = {
        pending: 'warning',
        running: 'info',
        success: 'success',
        failed: 'error',
        timeout: 'error',
        stopped: 'default',
      }
      const labelMap: Record<string, string> = {
        pending: '待执行',
        running: '执行中',
        success: '成功',
        failed: '失败',
        timeout: '超时',
        stopped: '已停止',
      }
      // 执行中：使用 NProgress 自带的动画效果
      if (row.status === 'running') {
        return h('div', { style: 'width: 80px' }, [
          h(NProgress, {
            type: 'line',
            status: 'info',
            percentage: 100,
            showIndicator: false,
            processing: true,
            height: 6,
            borderRadius: 3
          }),
          h('span', { style: 'font-size: 12px; color: #2080f0; margin-top: 2px;' }, '执行中')
        ])
      }
      return h(NTag, { type: typeMap[row.status] || 'default' }, { default: () => labelMap[row.status] || row.status })
    }
  },
  {
    title: '开始时间',
    key: 'start_time',
    width: 180,
    render: (row: any) => row.start_time ? dayjs(row.start_time).format('YYYY-MM-DD HH:mm:ss') : '-'
  },
  {
    title: '结束时间',
    key: 'end_time',
    width: 180,
    render: (row: any) => row.end_time ? dayjs(row.end_time).format('YYYY-MM-DD HH:mm:ss') : '-'
  },
  { title: '耗时(秒)', key: 'duration', width: 70 },
  { title: '错误信息', key: 'error_message', width: 100, ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    fixed: 'right' as const,
    render: (row: any) => {
      const buttons = [
        h(
          NButton,
          {
            size: 'small',
            secondary: true,
            onClick: () => handleViewLog(row)
          },
          { default: () => '日志' }
        )
      ]

      if (row.status === 'running') {
        buttons.push(
          h(
            NPopconfirm,
            {
              onPositiveClick: () => handleStop(row)
            },
            {
              trigger: () => h(
                NButton,
                {
                  size: 'small',
                  type: 'error',
                  secondary: true,
                  style: 'margin-left: 6px'
                },
                { default: () => '停止' }
              ),
              default: () => '确定要停止该任务吗？'
            }
          )
        )
      }

      return buttons
    }
  }
]

const logModalVisible = ref(false)
const currentLog = ref('')
const currentExecutionId = ref<number | null>(null)
const currentExecutionStatus = ref('')

// Log viewer state
const logTotalLines = ref(0)
const logLoadedLines = ref(0)
const logHasMore = ref(false)
const logLoading = ref(false)
const logOffset = ref(0)

// Search state
const searchKeyword = ref('')
const matchIndices = ref<{lineIdx: number, matchIdxInLine: number}[]>([])
const currentMatchIndex = ref(-1)
const searchDebounceTimer = ref<ReturnType<typeof setTimeout> | null>(null)

// Auto-polling state
const logPollingInterval = ref<ReturnType<typeof setInterval> | null>(null)
const autoScroll = ref(true)
const isPolling = ref(false)
const logContainerRef = ref<HTMLElement | null>(null)

const matchCount = computed(() => matchIndices.value.length)

// Watch searchKeyword for auto-search with debounce
watch(searchKeyword, () => {
  if (searchDebounceTimer.value) {
    clearTimeout(searchDebounceTimer.value)
  }
  searchDebounceTimer.value = setTimeout(() => {
    handleLogSearch()
  }, 300)
})

const highlightedLog = computed(() => {
  if (!searchKeyword.value.trim() || !currentLog.value) {
    return currentLog.value
  }
  const keyword = searchKeyword.value.trim()
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${escaped})`, 'gi')
  const lines = currentLog.value.split('\n')

  // Get current match info
  const currentMatch = matchIndices.value[currentMatchIndex.value]
  const currentMatchLineIdx = currentMatch?.lineIdx ?? -1
  const currentMatchIdxInLine = currentMatch?.matchIdxInLine ?? -1

  const highlightedLines = lines.map((line, lineIdx) => {
    let matchCountInLine = 0
    return line.replace(regex, (match) => {
      const isCurrentMatch = lineIdx === currentMatchLineIdx && matchCountInLine === currentMatchIdxInLine
      matchCountInLine++

      const style = isCurrentMatch
        ? 'background: #ff7043; color: #fff; padding: 0 2px; border-radius: 2px; box-shadow: 0 0 4px #ff7043;'
        : 'background: #ffd54f; color: #000; padding: 0 2px; border-radius: 2px;'
      const idAttribute = isCurrentMatch ? 'id="current-log-match"' : ''
      return `<mark ${idAttribute} style="${style}">${match}</mark>`
    })
  })

  return highlightedLines.join('\n')
})

const handleViewLog = async (row: any) => {
  currentExecutionId.value = row.id
  currentExecutionStatus.value = row.status
  logModalVisible.value = true
  logLoading.value = true
  currentLog.value = ''
  logOffset.value = 0
  searchKeyword.value = ''
  matchIndices.value = []
  currentMatchIndex.value = -1

  try {
    const res: any = await api.get(`/executions/${row.id}/logs`, { params: { lines: 200 } })
    currentLog.value = res.content || ''
    logTotalLines.value = res.total_lines || 0
    logLoadedLines.value = res.loaded_lines || 0
    logHasMore.value = res.has_more || false

    // Start polling if task is running
    if (row.status === 'running') {
      startLogPolling()
    }

    await nextTick()
    scrollToBottom()
  } catch (error) {
    currentLog.value = '获取日志失败'
  } finally {
    logLoading.value = false
  }
}

const loadMoreLogs = async () => {
  if (!currentExecutionId.value || logLoading.value) return
  logLoading.value = true

  try {
    const newOffset = logOffset.value + logLoadedLines.value
    const res: any = await api.get(`/executions/${currentExecutionId.value}/logs`, {
      params: { lines: 500, offset: newOffset }
    })

    if (res.content) {
      currentLog.value = res.content + currentLog.value
      logLoadedLines.value += res.loaded_lines || 0
      logHasMore.value = res.has_more || false
      logOffset.value = newOffset
    }
  } catch (error) {
    message.error('加载更多日志失败')
  } finally {
    logLoading.value = false
  }
}

const startLogPolling = () => {
  if (logPollingInterval.value) return
  isPolling.value = true

  logPollingInterval.value = setInterval(async () => {
    if (!currentExecutionId.value) return

    try {
      const res: any = await api.get(`/executions/${currentExecutionId.value}/logs`, {
        params: { after_line: logTotalLines.value }
      })

      if (res.content) {
        currentLog.value += res.content
        logTotalLines.value = res.total_lines || logTotalLines.value
        logLoadedLines.value += res.loaded_lines || 0

        if (autoScroll.value) {
          await nextTick()
          scrollToBottom()
        }
      }

      // Check if task is still running
      const execRes: any = await api.get(`/executions/${currentExecutionId.value}`)
      if (execRes.status !== 'running') {
        stopLogPolling()
        currentExecutionStatus.value = execRes.status
      }
    } catch (error) {
      console.error('Log polling error:', error)
    }
  }, 2000)
}

const stopLogPolling = () => {
  if (logPollingInterval.value) {
    clearInterval(logPollingInterval.value)
    logPollingInterval.value = null
  }
  isPolling.value = false
}

const scrollToBottom = () => {
  if (logContainerRef.value) {
    logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
  }
}

const handleLogSearch = () => {
  if (!searchKeyword.value.trim() || !currentLog.value) {
    matchIndices.value = []
    currentMatchIndex.value = -1
    return
  }

  const keyword = searchKeyword.value.trim().toLowerCase()
  const lines = currentLog.value.split('\n')
  const indices: {lineIdx: number, matchIdxInLine: number}[] = []

  // Find all individual match occurrences
  lines.forEach((line, lineIdx) => {
    const lineLower = line.toLowerCase()
    let pos = 0
    let matchIdxInLine = 0
    while ((pos = lineLower.indexOf(keyword, pos)) !== -1) {
      indices.push({ lineIdx, matchIdxInLine })
      matchIdxInLine++
      pos += keyword.length
    }
  })

  matchIndices.value = indices

  // Find the match closest to current scroll position
  if (indices.length > 0 && logContainerRef.value) {
    const lineHeight = 19.5
    const currentScrollTop = logContainerRef.value.scrollTop
    const visibleCenterLine = Math.floor((currentScrollTop + logContainerRef.value.clientHeight / 2) / lineHeight)

    // Find the closest match to the visible center
    let closestIdx = 0
    let minDistance = Math.abs(indices[0].lineIdx - visibleCenterLine)

    indices.forEach((match, i) => {
      const distance = Math.abs(match.lineIdx - visibleCenterLine)
      if (distance < minDistance) {
        minDistance = distance
        closestIdx = i
      }
    })

    currentMatchIndex.value = closestIdx
  } else {
    currentMatchIndex.value = indices.length > 0 ? 0 : -1
  }
}

const prevMatch = () => {
  if (matchCount.value === 0) return
  currentMatchIndex.value = (currentMatchIndex.value - 1 + matchCount.value) % matchCount.value
  scrollToMatch()
}

const nextMatch = () => {
  if (matchCount.value === 0) return
  currentMatchIndex.value = (currentMatchIndex.value + 1) % matchCount.value
  scrollToMatch()
}

const scrollToMatch = async () => {
  await nextTick()
  if (!logContainerRef.value || matchIndices.value.length === 0) return

  const el = document.getElementById('current-log-match')
  if (el) {
    const container = logContainerRef.value
    // Calculate the relative offset
    const targetScrollTop = el.offsetTop - container.offsetTop - container.clientHeight / 2 + el.clientHeight / 2

    container.scrollTo({
      top: Math.max(0, targetScrollTop),
      behavior: 'smooth'
    })
  }
}

const handleLogModalClose = () => {
  stopLogPolling()
  logModalVisible.value = false
}

const handleStop = async (row: any) => {
  try {
    await api.post(`/executions/${row.id}/stop`)
    message.success('停止指令已发送')
    fetchExecutions()
  } catch (error: any) {
    message.error(error.message || '停止失败')
  }
}

const fetchTasks = async (query?: string) => {
    try {
        const res: any = await taskApi.list({ page_size: 100, name: query })
        const tasks = res.items || []
        const newOptions = [
            { label: '全部任务', value: '' },
            ...tasks.map((t: any) => ({ label: t.name, value: t.id }))
        ]

        // Preserve selected task label ONLY if we are NOT searching (query is empty)
        // This ensures normal filtering logic during active search.
        if (!query && selectedTaskId.value && !newOptions.some(opt => opt.value === selectedTaskId.value)) {
            const currentSelected = taskOptions.value.find(opt => opt.value === selectedTaskId.value)
            if (currentSelected) {
                newOptions.push(currentSelected)
            }
        }
        taskOptions.value = newOptions
    } catch (error) {
        console.error('获取任务列表失败', error)
    }
}

const fetchExecutions = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
    }
    if (selectedStatus.value) {
      params.status = selectedStatus.value
    }
    if (selectedTaskId.value) {
      params.task_id = selectedTaskId.value
    }
    if (dateRange.value) {
      params.start_time = dayjs(dateRange.value[0]).format('YYYY-MM-DD HH:mm:ss')
      params.end_time = dayjs(dateRange.value[1]).format('YYYY-MM-DD HH:mm:ss')
    }
    const res: any = await api.get('/executions', { params })
    executions.value = res.items || []
    pagination.value.itemCount = res.total || 0
  } catch (error) {
    console.error('获取执行记录失败', error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.value.page = 1
  fetchExecutions()
}

const handlePageChange = (page: number) => {
  pagination.value.page = page
  fetchExecutions()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.value.pageSize = pageSize
  pagination.value.page = 1
  fetchExecutions()
}

const handleStatusChange = () => {
  handleSearch()
}

const handleTaskShow = (show: boolean) => {
  if (show) {
    fetchTasks()
  }
}

// 智能轮询：当有执行中或待执行的任务时自动刷新
const pollInterval = ref<ReturnType<typeof setInterval> | null>(null)

const hasActiveTasks = computed(() => {
  return executions.value.some((e: any) => e.status === 'running' || e.status === 'pending')
})

watch(hasActiveTasks, (newVal) => {
  if (newVal && !pollInterval.value) {
    // 开始轮询
    pollInterval.value = setInterval(() => {
      fetchExecutions()
    }, 3000)
  } else if (!newVal && pollInterval.value) {
    // 停止轮询
    clearInterval(pollInterval.value)
    pollInterval.value = null
  }
}, { immediate: true })

onUnmounted(() => {
  if (pollInterval.value) {
    clearInterval(pollInterval.value)
  }
  stopLogPolling()
})

onMounted(() => {
    fetchTasks()
    fetchExecutions()
})
</script>

<template>
  <div >
    <n-card title="执行记录">
      <template #header-extra>
        <n-space>
          <n-select
            v-model:value="selectedTaskId"
            :options="taskOptions"
            placeholder="搜索/选择任务"
            style="width: 200px;"
            filterable
            clearable
            remote
            @search="fetchTasks"
            @update:show="handleTaskShow"
            @update:value="handleSearch"
          />
          <n-date-picker
            v-model:value="dateRange"
            type="datetimerange"
            clearable
            style="width: 380px;"
            @update:value="handleSearch"
          />
          <n-select
            v-model:value="selectedStatus"
            :options="statusOptions"
            style="width: 120px;"
            @update:value="handleStatusChange"
          />
          <n-button type="primary" @click="handleSearch">查询</n-button>
          <n-button @click="handleSearch">刷新</n-button>
        </n-space>
      </template>
      <n-data-table
        :columns="columns"
        :data="executions"
        :loading="loading"
        :pagination="pagination"
        :bordered="false"
        :scroll-x="1300"
        remote
        @update:page="handlePageChange"
        @update:page-size="handlePageSizeChange"
      />
    </n-card>

    <n-modal
      v-model:show="logModalVisible"
      preset="dialog"
      title="执行日志"
      style="width: 900px;"
      :on-after-leave="stopLogPolling"
    >
      <!-- Search bar -->
      <div style="margin-bottom: 12px;">
        <n-space align="center">
          <n-input
            v-model:value="searchKeyword"
            placeholder="输入关键词搜索日志..."
            clearable
            style="width: 300px;"
            @keyup.enter="handleLogSearch"
            @clear="handleLogSearch"
          >
            <template #prefix>
              <n-icon :component="SearchOutline" />
            </template>
          </n-input>
          <n-button type="primary" @click="handleLogSearch">搜索</n-button>
          <n-space v-if="matchCount > 0" align="center" :size="8">
            <span style="font-size: 13px; color: #666;">{{ currentMatchIndex + 1 }} / {{ matchCount }} 匹配</span>
            <n-button size="small" tertiary @click="prevMatch">
              <template #icon><n-icon :component="ArrowUpOutline" /></template>
            </n-button>
            <n-button size="small" tertiary @click="nextMatch">
              <template #icon><n-icon :component="ArrowDownOutline" /></template>
            </n-button>
          </n-space>
        </n-space>
      </div>

      <!-- Log stats bar -->
      <div style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
        <n-space align="center" :size="12">
          <span style="font-size: 13px; color: #999;">
            显示 {{ logLoadedLines }} 行 / 共 {{ logTotalLines }} 行
          </span>
          <n-button v-if="logHasMore" size="small" :loading="logLoading" @click="loadMoreLogs">
            加载更多
          </n-button>
        </n-space>
        <n-space align="center" :size="8">
          <span v-if="isPolling" style="font-size: 12px; color: #18a058;">● 实时更新中</span>
          <n-switch v-model:value="autoScroll" size="small">
            <template #checked>自动滚动</template>
            <template #unchecked>自动滚动</template>
          </n-switch>
        </n-space>
      </div>

      <!-- Log content -->
      <div
        ref="logContainerRef"
        style="background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 4px; height: 450px; overflow-y: auto;"
      >
        <pre v-if="!searchKeyword.trim()" style="margin: 0; white-space: pre-wrap; font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; line-height: 1.5;">{{ currentLog || '暂无日志' }}</pre>
        <pre v-else v-html="highlightedLog" style="margin: 0; white-space: pre-wrap; font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; line-height: 1.5;"></pre>
      </div>

      <template #action>
        <n-space justify="end">
          <n-button @click="handleViewLog({id: currentExecutionId, status: currentExecutionStatus})">刷新</n-button>
          <n-button @click="handleLogModalClose">关闭</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>
