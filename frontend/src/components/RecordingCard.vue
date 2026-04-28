<template>
  <el-card class="recording-card" shadow="hover" :body-style="{ padding: '0' }">
    <div class="card-thumbnail" @click="handlePlay">
      <img v-if="item.thumbnail" :src="item.thumbnail" :alt="item.filename" loading="lazy" />
      <div v-else class="thumbnail-placeholder">
        <el-icon :size="32"><VideoPlay /></el-icon>
      </div>
      <div class="thumbnail-overlay">
        <el-icon :size="36"><VideoPlay /></el-icon>
      </div>
    </div>
    <div class="card-info">
      <div class="card-title" :title="item.filename">{{ formatTime(item.created_at) }}</div>
      <div class="card-meta">
        <span>{{ item.size_human }}</span>
        <span v-if="item.duration">{{ formatDuration(item.duration) }}</span>
      </div>
      <div class="card-actions">
        <el-button size="small" :icon="Download" @click="handleDownload" text type="primary" />
        <el-popconfirm title="确定删除此录像？" confirm-button-text="删除" cancel-button-text="取消" @confirm="handleDelete">
          <template #reference>
            <el-button size="small" :icon="Delete" text type="danger" />
          </template>
        </el-popconfirm>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts" generic="T extends RecordingItem">
import { VideoPlay, Download, Delete } from '@element-plus/icons-vue'
import type { RecordingItem } from '../api'
import { getDownloadUrl } from '../api'

const props = defineProps<{ item: RecordingItem }>()
const emit = defineEmits<{ delete: [path: string]; play: [path: string] }>()

function formatTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDuration(sec: number) {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function handlePlay() {
  emit('play', props.item.path)
}

function handleDownload() {
  const url = getDownloadUrl(props.item.path)
  window.open(url, '_blank')
}

function handleDelete() {
  emit('delete', props.item.path)
}
</script>

<style scoped>
.recording-card {
  background: var(--bg-secondary);
  border-color: var(--border);
  transition: transform 0.2s, border-color 0.2s;
}
.recording-card:hover {
  transform: translateY(-2px);
  border-color: var(--accent);
}

.card-thumbnail {
  position: relative;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: #000;
  cursor: pointer;
}
.card-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumbnail-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}
.thumbnail-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0.5);
  opacity: 0;
  transition: opacity 0.2s;
  color: #fff;
}
.card-thumbnail:hover .thumbnail-overlay {
  opacity: 1;
}

.card-info {
  padding: 10px 12px;
}
.card-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-meta {
  display: flex;
  gap: 12px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}
.card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  margin-top: 6px;
}
</style>