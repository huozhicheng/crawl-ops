<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, inject, Ref, nextTick } from 'vue'
import {
    NCard, NGrid, NGridItem, NStatistic, NIcon,
    NTag, NProgress, NScrollbar, NSelect, NList, NListItem, NAlert, NEmpty
} from 'naive-ui'
import {
    FolderOutline,
    PlayCircleOutline,
    ServerOutline,
    TimeOutline
} from '@vicons/ionicons5'
import { dashboardApi, statisticsApi } from '@/api'
import * as echarts from 'echarts'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'

const router = useRouter()

// 注入来自 MainLayout 的状态
const refreshInterval = inject<Ref<number>>('refreshInterval')
const lastRefreshTime = inject<Ref<string>>('lastRefreshTime')

// 状态
const loading = ref(false)
let refreshTimer: ReturnType<typeof setInterval> | null = null

// 数据
const overview = ref<any>({})
const nodesMonitor = ref<any[]>([])
const risks = ref<any>({ failures: [], offline_nodes: [], risky_proxies_count: 0 })
const upcoming = ref<any[]>([])
const trendData = ref<any>({ dates: [], success: [], failed: [] })
const distribution = ref<any[]>([])
const ranking = ref<any[]>([])
const selectedNodeId = ref<number | null>(null)
const nodeHistory = ref<any[]>([])

// 图表实例
let gaugeCharts: Record<string, echarts.ECharts | null> = {
    success: null,
    cpu: null,
    mem: null,
    disk: null
}
let trendChartInstance: echarts.ECharts | null = null
let distributionChartInstance: echarts.ECharts | null = null
let rankingChartInstance: echarts.ECharts | null = null
let nodeHistoryChartInstance: echarts.ECharts | null = null
let statusBarInstance: echarts.ECharts | null = null

// ===== 数据加载 =====
const fetchOverview = async () => {
    try {
        overview.value = (await dashboardApi.getOverview()) || {}
        nextTick(() => {
            renderGauges()
            renderStatusBar()
        })
    } catch (e) { console.error('获取概览失败', e) }
}

const fetchNodesMonitor = async () => {
    try {
        const res: any = await dashboardApi.getNodesMonitor()
        nodesMonitor.value = res.items || []
        if (nodesMonitor.value.length > 0 && !selectedNodeId.value) {
            selectedNodeId.value = nodesMonitor.value[0].id
        }
    } catch (e) { console.error('获取节点监控失败', e) }
}

const fetchRisks = async () => {
    try {
        risks.value = await dashboardApi.getRisks()
    } catch (e) { console.error('获取风险数据失败', e) }
}

const fetchUpcoming = async () => {
    try {
        const res: any = await dashboardApi.getUpcoming()
        upcoming.value = res.items || []
    } catch (e) { console.error('获取调度任务失败', e) }
}

const fetchTrend = async () => {
    try {
        trendData.value = await dashboardApi.getTrend(7)
        nextTick(() => renderTrendChart())
    } catch (e) { console.error('获取趋势数据失败', e) }
}

const fetchDistribution = async () => {
    try {
        distribution.value = (await statisticsApi.distribution()) as any
        nextTick(() => renderDistributionChart())
    } catch (e) { console.error('获取分布数据失败', e) }
}

const fetchRanking = async () => {
    try {
        ranking.value = (await statisticsApi.ranking()) as any
        nextTick(() => renderRankingChart())
    } catch (e) { console.error('获取排行数据失败', e) }
}

const fetchNodeHistory = async () => {
    if (!selectedNodeId.value) return
    try {
        const res: any = await dashboardApi.getNodeHistory(selectedNodeId.value, 60)
        nodeHistory.value = res.items || []
        renderNodeHistoryChart()
    } catch (e) { console.error('获取节点历史失败', e) }
}

// ===== 全量刷新 =====
const refreshAll = async () => {
    if (loading.value) return
    loading.value = true
    if (lastRefreshTime) {
        lastRefreshTime.value = dayjs().format('HH:mm:ss')
    }
    await Promise.all([
        fetchOverview(),
        fetchNodesMonitor(),
        fetchRisks(),
        fetchUpcoming(),
        fetchTrend(),
        fetchDistribution(),
        fetchRanking(),
    ])
    if (selectedNodeId.value) await fetchNodeHistory()
    loading.value = false
}

// ===== 图表渲染 =====
const getGaugeOption = (name: string, value: number, color: string) => ({
    title: {
        text: name,
        left: 'center',
        bottom: '10%',
        textStyle: {
            color: '#86909C',
            fontSize: 12,
            fontWeight: 'normal'
        }
    },
    series: [{
        type: 'gauge',
        startAngle: 210,
        endAngle: -30,
        radius: '85%',
        center: ['50%', '45%'],
        pointer: { show: false },
        progress: {
            show: true,
            overlap: false,
            roundCap: true,
            itemStyle: { color }
        },
        axisLine: { lineStyle: { width: 8, color: [[1, '#F2F3F5']] } },
        splitLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        data: [{ value }],
        detail: {
            fontSize: 20,
            color: '#1D2129',
            formatter: '{value}%',
            offsetCenter: [0, '0%'],
            fontWeight: 'bold'
        }
    }]
})

const renderGauges = () => {
    const ids = ['success-gauge', 'cpu-gauge', 'mem-gauge', 'disk-gauge']
    const colors = ['#00B42A', '#165DFF', '#722ED1', '#FF7D00']
    const values = [
        Number(overview.value.success_rate || 0),
        Number(overview.value.avg_cpu || 0),
        Number(overview.value.avg_mem || 0),
        Number(overview.value.avg_disk || 0)
    ]
    const names = ['成功率', 'CPU均值', '内存均值', '磁盘均值']

    ids.forEach((id, i) => {
        const dom = document.getElementById(id)
        if (!dom) return
        if (!gaugeCharts[id]) gaugeCharts[id] = echarts.init(dom)
        gaugeCharts[id]!.setOption(getGaugeOption(names[i], values[i], colors[i]))
    })
}

const renderStatusBar = () => {
    const dom = document.getElementById('status-bar')
    if (!dom) return
    if (!statusBarInstance) statusBarInstance = echarts.init(dom)

    const data = [
        { name: '成功', value: overview.value.success_count || 0, itemStyle: { color: '#00B42A' } },
        { name: '失败', value: overview.value.failed_count || 0, itemStyle: { color: '#F53F3F' } }
    ]

    statusBarInstance.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: 0, right: 0, top: 0, bottom: 0 },
        xAxis: { type: 'value', show: false },
        yAxis: { type: 'category', data: ['执行统计'], show: false },
        series: [
            {
                name: '成功',
                type: 'bar',
                stack: 'total',
                barWidth: 12,
                data: [data[0]],
                label: { show: true, position: 'inside', formatter: '{c}', fontSize: 10 },
                itemStyle: { borderRadius: [4, 0, 0, 4] }
            },
            {
                name: '失败',
                type: 'bar',
                stack: 'total',
                barWidth: 12,
                data: [data[1]],
                label: { show: true, position: 'inside', formatter: '{c}', fontSize: 10 },
                itemStyle: { borderRadius: [0, 4, 4, 0] }
            }
        ]
    })
}

const renderTrendChart = () => {
    const dom = document.getElementById('trend-chart')
    if (!dom) return
    if (!trendChartInstance) trendChartInstance = echarts.init(dom)
    const dates = trendData.value?.dates || []
    const success = trendData.value?.success || []
    const failed = trendData.value?.failed || []

    trendChartInstance.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['成功', '失败'], bottom: 0 },
        grid: { left: 50, right: 20, top: 40, bottom: 40 },
        xAxis: { type: 'category', data: dates },
        yAxis: { type: 'value' },
        series: [
            { name: '成功', type: 'line', smooth: true, data: success,
              itemStyle: { color: '#00B42A' }, areaStyle: { opacity: 0.1 } },
            { name: '失败', type: 'line', smooth: true, data: failed,
              itemStyle: { color: '#F53F3F' }, areaStyle: { opacity: 0.1 } }
        ]
    })
}

const renderDistributionChart = () => {
    const dom = document.getElementById('distribution-chart')
    if (!dom) return
    if (!distributionChartInstance) distributionChartInstance = echarts.init(dom)
    const colorMap: Record<string, string> = {
        success: '#00B42A', failed: '#F53F3F', running: '#165DFF',
        pending: '#FF7D00', timeout: '#86909C'
    }
    distributionChartInstance.setOption({
        tooltip: { trigger: 'item' },
        legend: { bottom: 0, show: true, icon: 'circle' },
        series: [{
            type: 'pie', radius: ['40%', '70%'],
            data: distribution.value.length > 0
                ? distribution.value.map(d => ({
                    value: d.value, name: d.name,
                    itemStyle: { color: colorMap[d.name] || '#86909C' }
                  }))
                : [{ value: 1, name: '暂无数据', itemStyle: { color: '#E5E6EB' } }]
        }]
    })
}

const renderRankingChart = () => {
    const dom = document.getElementById('ranking-chart')
    if (!dom) return
    if (!rankingChartInstance) rankingChartInstance = echarts.init(dom)
    rankingChartInstance.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: 100, right: 20, top: 10, bottom: 30 },
        xAxis: { type: 'value' },
        yAxis: {
            type: 'category',
            data: ranking.value.length > 0
                ? ranking.value.map((r: any) => r.name).reverse()
                : ['暂无数据']
        },
        series: [{
            type: 'bar',
            data: ranking.value.length > 0
                ? ranking.value.map((r: any) => r.count).reverse()
                : [0],
            itemStyle: { color: '#165DFF', borderRadius: [0, 4, 4, 0] }
        }]
    })
}

const renderNodeHistoryChart = () => {
    const dom = document.getElementById('node-history-chart')
    if (!dom) return
    if (!nodeHistoryChartInstance) nodeHistoryChartInstance = echarts.init(dom)
    const times = nodeHistory.value.map(h => dayjs(h.created_at).format('HH:mm'))
    nodeHistoryChartInstance.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['CPU', '内存', '磁盘'], bottom: 0 },
        grid: { left: 50, right: 20, top: 20, bottom: 40 },
        xAxis: { type: 'category', data: times.length > 0 ? times : ['--'] },
        yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
        series: [
            { name: 'CPU', type: 'line', smooth: true,
              data: nodeHistory.value.map(h => h.cpu_usage), itemStyle: { color: '#165DFF' } },
            { name: '内存', type: 'line', smooth: true,
              data: nodeHistory.value.map(h => h.memory_usage), itemStyle: { color: '#00B42A' } },
            { name: '磁盘', type: 'line', smooth: true,
              data: nodeHistory.value.map(h => h.disk_usage), itemStyle: { color: '#FF7D00' } }
        ]
    })
}

// ===== 自动刷新控制 =====
const setupTimer = (val: number) => {
    if (refreshTimer) clearInterval(refreshTimer)
    if (val > 0) {
        refreshTimer = setInterval(refreshAll, val * 1000)
    }
}

watch(() => refreshInterval?.value, (val) => {
    if (val !== undefined) setupTimer(val)
}, { immediate: true })

watch(selectedNodeId, () => fetchNodeHistory())

// 监听来自 MainLayout 的强制刷新事件
const handleRefreshEvent = () => refreshAll()

// ===== 生命周期 =====
onMounted(async () => {
    window.addEventListener('dashboard-refresh', handleRefreshEvent)
    await refreshAll()
})

onUnmounted(() => {
    window.removeEventListener('dashboard-refresh', handleRefreshEvent)
    if (refreshTimer) clearInterval(refreshTimer)
    Object.values(gaugeCharts).forEach(chart => chart?.dispose())
    trendChartInstance?.dispose()
    distributionChartInstance?.dispose()
    rankingChartInstance?.dispose()
    nodeHistoryChartInstance?.dispose()
    statusBarInstance?.dispose()
})

// 跳转失败任务
const goToExecution = (taskId: number) => {
    router.push({ name: 'executions', query: { task_id: taskId } })
}

// 节点选项
const nodeOptions = computed(() =>
    nodesMonitor.value.map(n => ({ label: n.name, value: n.id }))
)

// 网络流量
const networkRates = computed(() => {
    if (nodeHistory.value.length < 2) return { sent: '0.0', recv: '0.0' }
    const last = nodeHistory.value[nodeHistory.value.length - 1]
    const prev = nodeHistory.value[nodeHistory.value.length - 2]
    // 假设心跳间隔5s
    const sentRate = Math.max(0, (last.network_sent - prev.network_sent) / 5)
    const recvRate = Math.max(0, (last.network_recv - prev.network_recv) / 5)
    return { sent: (sentRate / 1024).toFixed(1), recv: (recvRate / 1024).toFixed(1) }
})

const handleResize = () => {
    Object.values(gaugeCharts).forEach(chart => chart?.resize())
    trendChartInstance?.resize()
    distributionChartInstance?.resize()
    rankingChartInstance?.resize()
    nodeHistoryChartInstance?.resize()
    statusBarInstance?.resize()
}

window.addEventListener('resize', handleResize)
onUnmounted(() => window.removeEventListener('resize', handleResize))
</script>

<template>
  <div class="dashboard-v2">
    <!-- 第一行: 仪表盘仪表盘 -->
    <n-grid :cols="4" :x-gap="16" class="section">
      <n-grid-item v-for="id in ['success-gauge', 'cpu-gauge', 'mem-gauge', 'disk-gauge']" :key="id">
        <n-card class="chart-card standard-card" :bordered="false">
          <div :id="id" style="height: 120px; width: 100%;"></div>
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- 第二行: 基础统计与状态 -->
    <n-grid :cols="12" :x-gap="16" :y-gap="16" class="section">
      <n-grid-item :span="5">
        <n-card title="核心统计" size="small" :bordered="false" class="standard-card">
          <n-grid :cols="3">
            <n-grid-item>
              <n-statistic label="总任务" :value="overview.total_tasks ?? '--'">
                <template #prefix><n-icon :component="PlayCircleOutline" color="#165DFF" /></template>
              </n-statistic>
            </n-grid-item>
            <n-grid-item>
              <n-statistic label="总项目" :value="overview.total_projects ?? '--'">
                <template #prefix><n-icon :component="FolderOutline" color="#00B42A" /></template>
              </n-statistic>
            </n-grid-item>
            <n-grid-item>
              <n-statistic label="在线节点" :value="overview.online_nodes ?? '--'">
                <template #prefix><n-icon :component="ServerOutline" color="#165DFF" /></template>
              </n-statistic>
            </n-grid-item>
          </n-grid>
          <div class="mini-stats-row">
            <div class="mini-stat-item">活跃任务: <n-tag type="success" size="small" round :bordered="false">{{ overview.active_tasks ?? 0 }}</n-tag></div>
            <div class="mini-stat-item">虚拟环境: <n-tag type="info" size="small" round :bordered="false">{{ overview.total_venvs ?? 0 }}</n-tag></div>
            <div class="mini-stat-item">可用代理: <n-tag type="warning" size="small" round :bordered="false">{{ overview.available_proxies ?? 0 }}</n-tag></div>
          </div>
        </n-card>
      </n-grid-item>
      <n-grid-item :span="7">
        <n-card title="执行历史统计" size="small" :bordered="false" class="standard-card">
          <template #header-extra>
              <span class="total-tag">总执行: {{ overview.total_executions || 0 }}</span>
          </template>
          <div id="status-bar" style="height: 40px"></div>
          <div class="status-footer">
            <div class="footer-item">今日执行: <b>{{ overview.today_executions || 0 }}</b></div>
            <div class="footer-item">平均耗时: <b>{{ overview.avg_duration || 0 }}</b>s</div>
            <div class="footer-item">成功率: <b>{{ overview.success_rate || 0 }}</b><span class="unit">%</span></div>
          </div>
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- 第三行: 项目/任务/执行 -->
    <n-grid :cols="12" :x-gap="16" :y-gap="16" class="section">
      <n-grid-item :span="4">
        <n-card title="项目活跃排行" size="small" :bordered="false" class="standard-card">
          <div v-show="ranking && ranking.length > 0" id="ranking-chart" style="height: 250px"></div>
          <n-empty v-if="!ranking || ranking.length === 0" description="暂无排行数据" style="height: 250px; justify-content: center" />
        </n-card>
      </n-grid-item>
      <n-grid-item :span="3">
        <n-card title="任务状态分布" size="small" :bordered="false" class="standard-card">
          <div v-show="distribution && distribution.length > 0" id="distribution-chart" style="height: 250px"></div>
          <n-empty v-if="!distribution || distribution.length === 0" description="暂无分布数据" style="height: 250px; justify-content: center" />
        </n-card>
      </n-grid-item>
      <n-grid-item :span="5">
        <n-card title="执行趋势 (7天)" size="small" :bordered="false" class="standard-card">
          <div v-show="trendData.dates && trendData.dates.length > 0" id="trend-chart" style="height: 250px"></div>
          <n-empty v-if="!trendData.dates || trendData.dates.length === 0" description="暂无执行趋势数据" style="height: 250px; justify-content: center" />
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- 工作节点区 -->
    <n-card title="工作节点监控" class="section" size="small">
      <n-scrollbar x-scrollable>
        <div class="nodes-row" v-if="nodesMonitor.length > 0">
          <n-card v-for="node in nodesMonitor" :key="node.id" class="node-card" size="small">
            <div class="node-header">
              <span class="node-name">{{ node.name }}</span>
              <n-tag :type="node.last_heartbeat ? 'success' : 'error'" size="small">
                {{ node.last_heartbeat ? '在线' : '离线' }}
              </n-tag>
            </div>
            <div class="node-metric">
              <span>CPU</span>
              <n-progress :percentage="node.cpu_usage || 0" :show-indicator="false"
                :color="node.cpu_usage > 80 ? '#F53F3F' : '#165DFF'" />
              <span class="metric-value">{{ node.cpu_usage || 0 }}%</span>
            </div>
            <div class="node-metric">
              <span>内存</span>
              <n-progress :percentage="node.memory_usage || 0" :show-indicator="false"
                :color="node.memory_usage > 80 ? '#F53F3F' : '#722ED1'" />
              <span class="metric-value">{{ node.memory_usage || 0 }}%</span>
            </div>
            <div class="node-metric">
              <span>磁盘</span>
              <n-progress :percentage="node.disk_usage || 0" :show-indicator="false"
                :color="node.disk_usage > 80 ? '#F53F3F' : '#FF7D00'" />
              <span class="metric-value">{{ node.disk_usage || 0 }}%</span>
            </div>
            <div class="node-footer">
              {{ node.last_heartbeat ? dayjs(node.last_heartbeat).format('HH:mm:ss') : '--' }}
            </div>
          </n-card>
        </div>
        <div v-else class="empty-placeholder">暂无在线节点</div>
      </n-scrollbar>
    </n-card>

    <!-- 底部: 历史与风险 -->
    <n-grid :cols="2" :x-gap="12" class="section">
      <n-grid-item>
        <n-card title="节点性能历史" size="small">
          <template #header-extra>
            <n-select v-model:value="selectedNodeId" :options="nodeOptions"
              placeholder="选择节点" size="small" style="width: 140px" />
          </template>
          <div v-if="selectedNodeId" class="network-info">
            网络: ↑{{ networkRates.sent }} KB/s  ↓{{ networkRates.recv }} KB/s
          </div>
          <div id="node-history-chart" style="height: 200px"></div>
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card title="运行风险 / 下步计划" size="small">
          <n-alert v-if="risks.failures?.length > 0" type="error" title="最近失败任务" style="margin-bottom: 8px">
            <n-list size="small">
              <n-list-item v-for="f in risks.failures.slice(0, 2)" :key="f.id"
                style="cursor: pointer;" @click="goToExecution(f.task_id)">
                {{ f.task_name }} ({{ dayjs(f.created_at).format('HH:mm') }})
              </n-list-item>
            </n-list>
          </n-alert>
          <n-alert v-if="risks.offline_nodes?.length > 0" type="warning" title="离线节点" style="margin-bottom: 8px">
            {{ risks.offline_nodes.map((n: any) => n.name).join(', ') }}
          </n-alert>
          <div v-if="upcoming.length > 0" class="upcoming-section">
            <div class="upcoming-title">待执行任务</div>
            <n-list size="small">
              <n-list-item v-for="t in upcoming.slice(0, 3)" :key="t.task_id">
                <div class="upcoming-item">
                  <n-icon :component="TimeOutline" />
                  <span>{{ t.task_name }}</span>
                  <span class="next-run">{{ dayjs(t.next_run).format('HH:mm:ss') }}</span>
                </div>
              </n-list-item>
            </n-list>
          </div>
          <div v-if="!risks.failures?.length && !risks.offline_nodes?.length && !upcoming.length" class="empty-placeholder">
            当前环境稳定，无警告
          </div>
        </n-card>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<style scoped>
.dashboard-v2 {
  padding: 8px;
  background-color: #F2F3F5;
  min-height: 100%;
}

.section {
  margin-bottom: 16px;
}

.standard-card {
  box-shadow: 0 2px 8px 0 rgba(0, 0, 0, 0.05);
  transition: box-shadow 0.3s ease;
  min-height: 200px; /* 统一统计卡片基础高度 */
  display: flex;
  flex-direction: column;
}

.chart-card {
  align-items: center;
  justify-content: center;
  padding: 8px 0;
  min-height: 136px;
}

.gauge-label {
  display: none; /* 移除外部标签，改为 ECharts title */
}

.mini-stats-row {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  padding: 0 4px;
}

.mini-stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #86909C;
}

.mini-stat-item :deep(.n-tag) {
  font-weight: 600;
}

.total-tag {
    font-size: 11px;
    background: #E5E6EB;
    padding: 1px 8px;
    border-radius: 12px;
    color: #1D2129;
}

.status-footer {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #86909C;
  border-top: 1px solid #F2F3F5;
  padding-top: 12px;
}

.footer-item {
    display: flex;
    align-items: baseline;
    gap: 2px;
}

.footer-item b {
    color: #1D2129;
    font-weight: 600;
    font-size: 14px;
}

.footer-item .unit {
    font-size: 10px;
    color: #C9CDD4;
}

.nodes-row {
  display: flex;
  flex-wrap: nowrap; /* 强制不换行 */
  gap: 12px;
  padding: 4px;
  width: max-content; /* 确保容器随内容拉伸 */
}

.node-card {
  width: 220px;
  min-width: 220px;
  flex-shrink: 0;
  box-shadow: 0 2px 6px 0 rgba(0, 0, 0, 0.04);
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.node-name {
  font-weight: 600;
  font-size: 13px;
  color: #1D2129;
}

.node-metric {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 11px;
}

.node-metric span:first-child {
  width: 32px;
  color: #4E5969;
}

.node-metric .n-progress {
  flex: 1;
}

.metric-value {
  width: 42px;
  text-align: right;
  color: #1D2129;
  font-weight: 500;
}

.node-footer {
  margin-top: 2px;
  font-size: 10px;
  color: #C9CDD4;
  text-align: right;
}

.network-info {
  font-size: 12px;
  color: #4E5969;
  margin-bottom: 8px;
  background: #F7F8FA;
  padding: 4px 12px;
  border-radius: 4px;
  display: inline-block;
}

.upcoming-section {
    margin-top: 8px;
}

.upcoming-title {
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 4px;
    color: #1D2129;
}

.upcoming-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
}

.next-run {
    margin-left: auto;
    color: #86909C;
    font-variant-numeric: tabular-nums;
}

.empty-placeholder {
  text-align: center;
  color: #C9CDD4;
  padding: 32px;
  font-size: 14px;
}

:deep(.n-card-header__main) {
  font-weight: 600 !important;
  font-size: 14px !important;
}

:deep(.n-statistic-label) {
  font-size: 12px;
  color: #86909C;
}

:deep(.n-statistic-value) {
  font-size: 22px;
  font-weight: 700;
  color: #1D2129;
}
</style>
