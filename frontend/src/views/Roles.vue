<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { NCard, NDataTable, NButton, NSpace, NTag, NModal, NForm, NFormItem, NInput, useMessage } from 'naive-ui'
import api from '@/api/request'

const message = useMessage()
const loading = ref(false)
const showModal = ref(false)
const roles = ref<any[]>([])

const formData = ref({
  name: '',
  code: '',
  description: '',
})

const columns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '角色名称', key: 'name' },
  { title: '角色代码', key: 'code', width: 120 },
  { title: '描述', key: 'description' },
  {
    title: '权限数量',
    key: 'permissions',
    width: 100,
    render: (row: any) => row.permissions?.length || 0
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render: (row: any) => {
      const isBuiltin = ['super_admin', 'project_admin', 'user'].includes(row.code)
      return h(NSpace, {}, {
        default: () => [
          h(NButton, {
            size: 'small',
            type: 'error',
            disabled: isBuiltin,
            onClick: () => handleDelete(row.id)
          }, { default: () => '删除' })
        ]
      })
    }
  },
]

const fetchRoles = async () => {
  loading.value = true
  try {
    const res: any = await api.get('/roles')
    roles.value = res.items
  } catch (error) {
    message.error('获取角色列表失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  formData.value = { name: '', code: '', description: '' }
  showModal.value = true
}

const handleSubmit = async () => {
  if (!formData.value.name || !formData.value.code) {
    message.warning('请填写完整信息')
    return
  }
  try {
    await api.post('/roles', formData.value)
    message.success('创建成功')
    showModal.value = false
    fetchRoles()
  } catch (error: any) {
    message.error(error.detail || '创建失败')
  }
}

const handleDelete = async (id: number) => {
  try {
    await api.delete(`/roles/${id}`)
    message.success('删除成功')
    fetchRoles()
  } catch (error: any) {
    message.error(error.detail || '删除失败')
  }
}

onMounted(fetchRoles)
</script>

<template>
  <div >
    <n-card title="角色管理">
      <template #header-extra>
        <n-button type="primary" @click="handleCreate">+ 添加角色</n-button>
      </template>

      <n-data-table :columns="columns" :data="roles" :loading="loading" :bordered="false" />
    </n-card>

    <!-- 添加角色弹窗 -->
    <n-modal v-model:show="showModal" preset="dialog" title="添加角色" style="width: 400px;">
      <n-form :model="formData" label-placement="left" label-width="80">
        <n-form-item label="角色名称">
          <n-input v-model:value="formData.name" placeholder="例如：运维人员" />
        </n-form-item>
        <n-form-item label="角色代码">
          <n-input v-model:value="formData.code" placeholder="例如：ops" />
        </n-form-item>
        <n-form-item label="描述">
          <n-input v-model:value="formData.description" type="textarea" :rows="2" />
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
