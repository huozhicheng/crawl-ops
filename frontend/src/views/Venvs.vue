<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, h } from 'vue'
import { NCard, NDataTable, NButton, NSpace, NTag, NModal, NForm, NFormItem, NInput, NDrawer, NDrawerContent, NList, NListItem, NThing, NUpload, NUploadDragger, NProgress, NAlert, NCollapse, NCollapseItem, useMessage, useDialog, NIcon } from 'naive-ui'
import { CloudUploadOutline } from '@vicons/ionicons5'
import type { UploadCustomRequestOptions } from 'naive-ui'
import { venvsApi } from '@/api'

const message = useMessage()
const loading = ref(false)
const showCreateModal = ref(false)
const showPackagesDrawer = ref(false)
const showBatchInstallModal = ref(false)
const showUploadModal = ref(false)
const items = ref<any[]>([])
const currentVenv = ref<any>(null)
const packages = ref<any[]>([])
const packagesLoading = ref(false)
const newPackageName = ref('')
const installing = ref(false)

// 批量安装相关
const batchPackages = ref('')
const batchInstalling = ref(false)
const batchResult = ref<any>(null)

const createForm = ref({
  name: '',
  description: ''
})

const columns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '环境名称', key: 'name', width: 150 },
  { title: 'Python版本', key: 'python_version', width: 100 },
  { title: '路径', key: 'path' },
  { title: '描述', key: 'description' },
  {
    title: '状态',
    key: 'status',
    width: 120,
    render: (row: any) => {
      if (row.install_status === 'installing') {
        return h(NSpace, { vertical: true, size: 'small' }, {
          default: () => [
            h(NTag, { type: 'warning' }, { default: () => '安装中...' }),
            row.install_message ? h('span', { style: 'font-size: 12px; color: #666;' }, row.install_message) : null
          ]
        })
      }
      return h(NTag, { type: 'success' }, { default: () => '正常' })
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    render: (row: any) => h(NSpace, {}, {
      default: () => [
        h(NButton, { size: 'small', type: 'primary', onClick: () => handleManagePackages(row) }, { default: () => '管理包' }),
        h(NButton, { size: 'small', type: 'error', onClick: () => handleDelete(row) }, { default: () => '删除' })
      ]
    })
  }
]

const fetchList = async () => {
    loading.value = true
    try {
        const res: any = await venvsApi.list()
        items.value = res.items
    } catch (error) {
        message.error('获取列表失败')
    } finally {
        loading.value = false
    }
}

const handleCreate = async () => {
    if (!createForm.value.name) return message.warning('请输入名称')
    try {
        await venvsApi.create(createForm.value)
        message.success('创建成功')
        showCreateModal.value = false
        fetchList()
    } catch (error: any) {
        message.error(error.detail || '创建失败')
    }
}

const dialog = useDialog()

const handleDelete = async (row: any) => {
  dialog.warning({
    title: '确认删除',
    content: '确定要删除该虚拟环境吗？此操作不可恢复。',
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await venvsApi.delete(row.id)
        message.success('删除成功')
        fetchList()
      } catch (error: any) {
        message.error('删除失败')
      }
    }
  })
}

const handleManagePackages = (row: any) => {
    currentVenv.value = row
    showPackagesDrawer.value = true
    fetchPackages(row.id)
}

const fetchPackages = async (id: number) => {
    packagesLoading.value = true
    try {
        const res: any = await venvsApi.listPackages(id)
        packages.value = res // assuming res is list or {packages: ...}
        // Check API response structure in venvs.py: venv_service returns list of dicts. venvs.py returns direct list?
        // In venvs.py: return packages (which is list from service)
    } catch (error) {
        message.error('获取包列表失败')
    } finally {
        packagesLoading.value = false
    }
}

const handleInstallPackage = async () => {
    if(!newPackageName.value) return
    installing.value = true
    try {
        await venvsApi.installPackage(currentVenv.value.id, newPackageName.value)
        message.success('安装成功')
        newPackageName.value = ''
        fetchPackages(currentVenv.value.id)
    } catch (error: any) {
        message.error(error.detail || '安装失败')
    } finally {
        installing.value = false
    }
}

// 批量安装
const handleBatchInstall = () => {
    batchPackages.value = ''
    batchResult.value = null
    showBatchInstallModal.value = true
}

const handleBatchInstallSubmit = async () => {
    if (!batchPackages.value.trim()) {
        message.warning('请输入要安装的包')
        return
    }

    const packages = batchPackages.value
        .split('\n')
        .map(line => line.trim())
        .filter(line => line && !line.startsWith('#'))

    if (packages.length === 0) {
        message.warning('没有有效的包')
        return
    }

    batchInstalling.value = true
    batchResult.value = null

    try {
        const res: any = await venvsApi.installPackagesBatch(currentVenv.value.id, packages)
        // 新的 API 立即返回，后台执行
        message.success(res.message || '安装任务已启动')
        showBatchInstallModal.value = false
        fetchList()  // 刷新列表以显示安装状态
    } catch (error: any) {
        message.error(error.detail || '批量安装失败')
    } finally {
        batchInstalling.value = false
    }
}

// 上传 requirements.txt
const handleUploadRequirements = () => {
    batchResult.value = null
    showUploadModal.value = true
}

const customRequest = async ({ file, onFinish, onError }: UploadCustomRequestOptions) => {
    try {
        const res: any = await venvsApi.uploadRequirements(currentVenv.value.id, file.file as File)
        // 新的 API 立即返回，后台执行
        message.success(res.message || '安装任务已启动')
        onFinish()
        showUploadModal.value = false
        fetchList()  // 刷新列表以显示安装状态
    } catch (error: any) {
        message.error(error.detail || '上传失败')
        onError()
    }
}

// 轮询逻辑：当有安装中的环境时自动刷新
const pollInterval = ref<ReturnType<typeof setInterval> | null>(null)

watch(() => items.value, (newItems) => {
    const hasInstalling = newItems.some((item: any) => item.install_status === 'installing')
    if (hasInstalling && !pollInterval.value) {
        // 开始轮询
        pollInterval.value = setInterval(() => {
            fetchList()
        }, 3000)
    } else if (!hasInstalling && pollInterval.value) {
        // 停止轮询
        clearInterval(pollInterval.value)
        pollInterval.value = null
    }
}, { deep: true })

onUnmounted(() => {
    if (pollInterval.value) {
        clearInterval(pollInterval.value)
    }
})

onMounted(fetchList)
</script>

<template>
  <div >
    <n-card title="虚拟环境管理">
      <template #header-extra>
        <n-button type="primary" @click="showCreateModal = true">+ 新建环境</n-button>
      </template>
      <n-data-table :columns="columns" :data="items" :loading="loading" />
    </n-card>

    <!-- 创建弹窗 -->
    <n-modal v-model:show="showCreateModal" preset="dialog" title="新建虚拟环境">
      <n-form>
        <n-form-item label="环境名称">
          <n-input v-model:value="createForm.name" placeholder="e.g. spider_env_1" />
        </n-form-item>
        <n-form-item label="描述">
          <n-input v-model:value="createForm.description" placeholder="用途描述" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button type="primary" @click="handleCreate">创建</n-button>
      </template>
    </n-modal>

    <!-- 包管理抽屉 -->
    <n-drawer v-model:show="showPackagesDrawer" :width="500">
      <n-drawer-content :title="`包管理 - ${currentVenv?.name}`">
        <n-space vertical>
           <!-- 单个安装 -->
           <n-space>
             <n-input v-model:value="newPackageName" placeholder="输入包名 (e.g. requests==2.31.0)" style="flex: 1;" />
             <n-button type="primary" :loading="installing" @click="handleInstallPackage">安装</n-button>
           </n-space>

           <!-- 批量操作按钮 -->
           <n-space>
             <n-button type="info" @click="handleBatchInstall">批量安装</n-button>
             <n-button type="success" @click="handleUploadRequirements">
               <template #icon>
                 <n-icon><CloudUploadOutline /></n-icon>
               </template>
               上传 requirements.txt
             </n-button>
           </n-space>

           <!-- 安装结果 -->
           <n-alert v-if="batchResult" :type="batchResult.failed === 0 ? 'success' : 'warning'" closable>
             <template #header>
               批量安装结果
             </template>
             <n-space vertical size="small">
               <div>总计: {{ batchResult.total }} 个包</div>
               <div>成功: {{ batchResult.success }} 个</div>
               <div>失败: {{ batchResult.failed }} 个</div>

               <n-collapse v-if="batchResult.details && batchResult.details.length > 0">
                 <n-collapse-item title="查看详情">
                   <n-list size="small">
                     <n-list-item v-for="(detail, index) in batchResult.details" :key="index">
                       <n-thing>
                         <template #header>
                           <n-space align="center">
                             <span>{{ detail.package }}</span>
                             <n-tag :type="detail.status === 'success' ? 'success' : 'error'" size="small">
                               {{ detail.status }}
                             </n-tag>
                           </n-space>
                         </template>
                         <template #description>
                           <span style="font-size: 12px; color: #666;">{{ detail.message }}</span>
                         </template>
                       </n-thing>
                     </n-list-item>
                   </n-list>
                 </n-collapse-item>
               </n-collapse>
             </n-space>
           </n-alert>

           <!-- 已安装包列表 -->
           <n-card title="已安装的包" size="small">
             <n-list bordered :loading="packagesLoading">
               <n-list-item v-for="pkg in packages" :key="pkg.name">
                 <n-thing :title="pkg.name" :description="`版本: ${pkg.version}`" />
               </n-list-item>
               <n-list-item v-if="packages.length === 0 && !packagesLoading">
                  <div style="text-align: center; color: #999">暂无已安装包</div>
               </n-list-item>
             </n-list>
           </n-card>
        </n-space>
      </n-drawer-content>
    </n-drawer>

    <!-- 批量安装弹窗 -->
    <n-modal v-model:show="showBatchInstallModal" preset="dialog" title="批量安装包" style="width: 600px;">
      <n-space vertical>
        <n-alert type="info">
          每行输入一个包名，支持指定版本。例如：
          <ul style="margin: 8px 0; padding-left: 20px;">
            <li>requests</li>
            <li>beautifulsoup4==4.12.2</li>
            <li>pandas>=1.5.0</li>
          </ul>
        </n-alert>

        <n-input
          v-model:value="batchPackages"
          type="textarea"
          placeholder="requests==2.31.0&#10;beautifulsoup4==4.12.2&#10;lxml&#10;pandas>=1.5.0"
          :rows="10"
        />

        <n-progress
          v-if="batchInstalling"
          type="line"
          status="info"
          :percentage="100"
          :show-indicator="false"
          processing
        />
      </n-space>

      <template #action>
        <n-space>
          <n-button @click="showBatchInstallModal = false" :disabled="batchInstalling">取消</n-button>
          <n-button type="primary" @click="handleBatchInstallSubmit" :loading="batchInstalling">
            开始安装
          </n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 上传 requirements.txt 弹窗 -->
    <n-modal v-model:show="showUploadModal" preset="dialog" title="上传 requirements.txt" style="width: 500px;">
      <n-space vertical>
        <n-alert type="info">
          上传 requirements.txt 文件，系统会自动解析并批量安装所有依赖包。
        </n-alert>

        <n-upload
          :custom-request="customRequest"
          accept=".txt,.requirements"
          :max="1"
        >
          <n-upload-dragger>
            <div style="margin-bottom: 12px">
              <n-icon size="48" :depth="3">
                <CloudUploadOutline />
              </n-icon>
            </div>
            <div style="font-size: 16px; margin-bottom: 8px">
              点击或拖拽文件到此区域上传
            </div>
            <div style="font-size: 14px; color: #999">
              支持 .txt 和 .requirements 文件
            </div>
          </n-upload-dragger>
        </n-upload>
      </n-space>
    </n-modal>
  </div>
</template>
