<template>
  <div class="zoom-control">
    <div class="zoom-header">
      <el-icon><Aim /></el-icon>
      <span>变焦控制</span>
    </div>
    <div class="zoom-body">
      <el-button :icon="ZoomOut" circle size="small" @click="handleZoomOut" :loading="loading" />
      <el-slider
        v-model="zoomValue"
        :min="zoomMin"
        :max="zoomMax"
        :step="zoomStep"
        vertical
        height="200px"
        :show-tooltip="false"
        @change="handleZoomChange"
      />
      <el-button :icon="ZoomIn" circle size="small" @click="handleZoomIn" :loading="loading" />
    </div>
    <div class="zoom-value">{{ zoomValue }}x</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Aim, ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import { getControl, zoomIn, zoomOut, zoomSet } from '../api'
import { ElMessage } from 'element-plus'

const zoomValue = ref(1)
const zoomMin = ref(1)
const zoomMax = ref(10)
const zoomStep = ref(1)
const loading = ref(false)

async function loadZoomControl() {
  for (const name of ['zoom_absolute', 'zoom_relative']) {
    try {
      const { data } = await getControl(name)
      if (data && data.name) {
        zoomMin.value = data.min_val
        zoomMax.value = data.max_val
        zoomStep.value = data.step || 1
        zoomValue.value = data.current_val
        return
      }
    } catch {
      // Try the next supported V4L2 zoom control name.
    }
  }
}

async function handleZoomIn() {
  loading.value = true
  try {
    const { data } = await zoomIn(zoomStep.value)
    if (data?.zoom !== undefined) zoomValue.value = data.zoom
  } catch {
    ElMessage.error('变焦操作失败')
  } finally {
    loading.value = false
  }
}

async function handleZoomOut() {
  loading.value = true
  try {
    const { data } = await zoomOut(zoomStep.value)
    if (data?.zoom !== undefined) zoomValue.value = data.zoom
  } catch {
    ElMessage.error('变焦操作失败')
  } finally {
    loading.value = false
  }
}

async function handleZoomChange(val: number) {
  loading.value = true
  try {
    const { data } = await zoomSet(val)
    if (data?.zoom !== undefined) zoomValue.value = data.zoom
  } catch {
    ElMessage.error('变焦设置失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadZoomControl)
</script>

<style scoped>
.zoom-control {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 16px 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border);
}
.zoom-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}
.zoom-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.zoom-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
}

:deep(.el-slider__bar) { background: var(--accent); }
:deep(.el-slider__button) { border-color: var(--accent); }
</style>
