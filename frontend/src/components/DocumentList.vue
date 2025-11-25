<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { DocumentRecord } from '../api'
import { listDocuments } from '../api'

const props = defineProps<{
  isAuthenticated: boolean
}>()

const emit = defineEmits<{
  'document-selected': [string]
}>()

const documents = ref<DocumentRecord[]>([])
const loading = ref(false)

const fetchDocuments = async () => {
  if (!props.isAuthenticated) {
    documents.value = []
    return
  }
  loading.value = true
  try {
    const { data } = await listDocuments()
    documents.value = data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '获取文档列表失败')
  } finally {
    loading.value = false
  }
}

const handleSelect = (row: DocumentRecord) => {
  emit('document-selected', row.id)
}

watch(
  () => props.isAuthenticated,
  (authed) => {
    if (authed) {
      fetchDocuments()
    } else {
      documents.value = []
    }
  },
  { immediate: true },
)

defineExpose({
  refreshDocuments: fetchDocuments,
})
</script>

<template>
  <div class="documents-panel">
    <div class="panel-header">
      <div>
        <h3>已上传文档</h3>
        <p class="sub-text">点击列表可直接跳转到 Q&A</p>
      </div>
      <el-button type="primary" link :disabled="loading || !isAuthenticated" @click="fetchDocuments">
        刷新
      </el-button>
    </div>

    <div v-if="!isAuthenticated" class="empty-state">
      <el-empty description="请先登录后查看文档列表" />
    </div>
    <div v-else>
      <el-table
        v-loading="loading"
        :data="documents"
        border
        size="small"
        empty-text="暂无文档"
        @row-click="handleSelect"
        class="documents-table"
      >
        <el-table-column prop="source_value" label="文件名" min-width="200">
          <template #default="{ row }">
            <span class="doc-name">{{ row.source_value || row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : 'info'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="180">
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click.stop="handleSelect(row)">前往 Q&A</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.documents-panel {
  margin-top: 32px;
  padding: 24px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.panel-header h3 {
  margin: 0;
  font-size: 18px;
}

.sub-text {
  margin: 0;
  color: #909399;
  font-size: 13px;
}

.documents-table :deep(.el-table__row) {
  cursor: pointer;
}

.documents-table :deep(.el-table__row:hover) {
  background-color: #f5f7fa;
}

.doc-name {
  font-weight: 500;
  color: #303133;
}
</style>

