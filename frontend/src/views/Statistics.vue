<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NGrid, NGridItem, useMessage } from 'naive-ui'
import { statisticsApi } from '@/api'
import * as echarts from 'echarts'

const message = useMessage()
const trendRef = ref<HTMLElement>()
const rankingRef = ref<HTMLElement>()
const distributionRef = ref<HTMLElement>()

const initCharts = async () => {
    try {
        // 1. Trend Chart
        const trendData = await statisticsApi.trend(7)
        const trendChart = echarts.init(trendRef.value!)
        trendChart.setOption({
            title: { text: '近7天执行趋势' },
            tooltip: { trigger: 'axis' },
            legend: { data: ['成功', '失败'] },
            xAxis: { type: 'category', data: (trendData as any).dates },
            yAxis: { type: 'value' },
            series: [
                { name: '成功', type: 'line', data: (trendData as any).success, itemStyle: { color: '#67C23A' } },
                { name: '失败', type: 'line', data: (trendData as any).failed, itemStyle: { color: '#F56C6C' } }
            ]
        })

        // 2. Ranking Chart
        const rankingData = await statisticsApi.ranking()
        const rankingChart = echarts.init(rankingRef.value!)
        rankingChart.setOption({
            title: { text: '项目活跃度TOP10' },
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            xAxis: { type: 'category', data: (rankingData as any).map((i: any) => i.name) },
            yAxis: { type: 'value' },
            series: [{ type: 'bar', data: (rankingData as any).map((i: any) => i.count), itemStyle: { color: '#409EFF' } }]
        })

        // 3. Distribution Chart
        const distData = await statisticsApi.distribution()
        const distChart = echarts.init(distributionRef.value!)
        distChart.setOption({
            title: { text: '任务状态分布' },
            tooltip: { trigger: 'item' },
            legend: { bottom: '5%' },
            series: [
                {
                    type: 'pie',
                    radius: ['40%', '70%'],
                    data: (distData as any).map((i: any) => ({
                        name: i.name,
                        value: i.value,
                        itemStyle: {
                            color: i.name === 'success' ? '#67C23A' :
                                   i.name === 'failed' ? '#F56C6C' :
                                   i.name === 'running' ? '#E6A23C' : '#909399'
                        }
                    }))
                }
            ]
        })

        // Resize observer
        window.addEventListener('resize', () => {
            trendChart.resize()
            rankingChart.resize()
            distChart.resize()
        })

    } catch (error) {
        message.warning('部分统计数据获取失败')
        console.error(error)
    }
}

onMounted(() => {
    // wait for DOM
    setTimeout(initCharts, 100)
})
</script>

<template>
    <div style="padding-bottom: 20px">
        <n-grid :x-gap="12" :y-gap="12" cols="1 800:2">
            <n-grid-item span="2">
                <n-card>
                    <div ref="trendRef" style="height: 350px"></div>
                </n-card>
            </n-grid-item>
            <n-grid-item>
                <n-card>
                    <div ref="rankingRef" style="height: 350px"></div>
                </n-card>
            </n-grid-item>
            <n-grid-item>
                <n-card>
                    <div ref="distributionRef" style="height: 350px"></div>
                </n-card>
            </n-grid-item>
        </n-grid>
    </div>
</template>
