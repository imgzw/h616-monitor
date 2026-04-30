<template>
  <div class="recordings-view">
    <div class="recordings-header">
      <h2>录像管理</h2>
      <div class="header-actions">
        <el-date-picker
          v-model="dateFilter"
          type="date"
          placeholder="按日期筛选"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          clearable
          @change="loadRecordings"
        />
        <el-button type="danger" plain :icon="Delete" @click="handleCleanup">
          清理磁盘
        </el-button>
      </div>
    </div>

    <div class="storage-bar">
      <div class="storage-info">
        <span>磁盘使用: {{ formatSize(storage.used_bytes) }} / {{ formatSize(storage.total_bytes) }}</span>
        <span>{{ storage.usage_percent.toFixed(1) }}%</span>
      </div>
      <el-progress
        :percentage="storage.usage_percent"
        :stroke-width="12"
        :color="diskColorVal"
        :show-text="false"
      />
    </div>

    <div v-if="loading" class="loading-container">
      <el-icon :size="32" class="is-loading"><Loading /></el-icon>
    </div>
    <div v-else-if="recordings.length === 0" class="empty-container">
      <el-empty description="暂无录像" />
    </div>
    <div v-else class="recordings-grid">
      <RecordingCard
        v-for="item in recordings"
        :key="item.path"
        :item="item"
        @delete="handleDelete"
        @play="handlePlay"
      />
    </div>

    <div v-if="total > pageSize" class="pagination-container">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="loadRecordings"
      />
    </div>

    <el-dialog v-model="playDialogVisible" title="播放录像" width="80%" destroy-on-close>
      <video
        v-if="playDialogVisible"
        :src="playUrl"
        controls
        autoplay
        class="playback-video"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Delete, Loading } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import RecordingCard from '../components/RecordingCard.vue'
import {
  getRecordings,
  deleteRecording,
  triggerCleanup,
  getStorage,
  getDownloadUrl,
  type RecordingItem,
  type StorageInfo as StorageInfoType,
} from '../api'
import { formatSize, diskColor } from '../utils/format'

const recordings = ref<RecordingItem[]>([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)
const dateFilter = ref<string | null>(null)
const playDialogVisible = ref(false)
const playUrl = ref('')

const storage = reactive<StorageInfoType>({
  total_bytes: 0,
  used_bytes: 0,
  free_bytes: 0,
  usage_percent: 0,
  recordings_bytes: 0,
  recordings_count: 0,
})

async function loadRecordings() {
  loading.value = true
  try {
    const { data } = await getRecordings(currentPage.value, pageSize, dateFilter.value ?? undefined)
    recordings.value = data.items
    total.value = data.total
  } catch {
    ElMessage.error('加载录像列表失败')
  } finally {
    loading.value = false
  }
}

async function loadStorage() {
  try {
    const { data } = await getStorage()
    Object.assign(storage, data)
  } catch {
    // silent
  }
}

async function handleDelete(path: string) {
  try {
    await deleteRecording(path)
    ElMessage.success('录像已删除')
    loadRecordings()
    loadStorage()
  } catch {
    ElMessage.error('删除失败')
  }
}

function handlePlay(path: string) {
  playUrl.value = getDownloadUrl(path)
  playDialogVisible.value = true
}

async function handleCleanup() {
  try {
    await ElMessageBox.confirm('将自动清理最旧录像直到磁盘使用率低于70%', '磁盘清理')
    const { data } = await triggerCleanup()
    ElMessage.success(`已清理 ${data.deleted_files} 个文件`)
    loadRecordings()
    loadStorage()
  } catch {
    // cancelled
  }
}

const diskColorVal = computed(() => diskColor(storage.usage_percent))

onMounted(() => {
  loadRecordings()
  loadStorage()
})
</script>

<style scoped>
.recordings-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.recordings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 10px;
}
.recordings-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}
.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}
.storage-bar {
  margin-bottom: 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
}
.storage-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}
.loading-container,
.empty-container {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  min-height: 280px;
}
.recordings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
  flex: 1;
  align-content: start;
}
.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 16px;
  padding-bottom: 8px;
}
.playback-video {
  width: 100%;
  max-height: 70vh;
  background: #000;
  border-radius: var(--radius-sm);
}

@media (max-width: 768px) {
  .recordings-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 10px;
  }
  .header-actions {
    width: 100%;
  }
  .header-actions .el-date-picker {
    flex: 1;
    min-width: 0;
  }
}
@media (max-width: 480px) {
  .recordings-grid {
    grid-template-columns: 1fr;
  }
}
</style>