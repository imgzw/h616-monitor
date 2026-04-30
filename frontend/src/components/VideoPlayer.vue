<template>
  <div class="video-player" ref="containerRef">
    <img
      v-if="mode === 'mjpeg'"
      :src="mjpegUrl"
      class="video-element"
      @load="onMjpegFirstFrame"
      @error="onMjpegError"
    />
    <video
      v-else
      ref="videoRef"
      autoplay
      playsinline
      muted
      class="video-element"
      @loadedmetadata="onVideoReady"
    />
    <div v-if="!connected" class="video-overlay">
      <el-icon :size="48" class="connecting-icon"><VideoCamera /></el-icon>
      <p>{{ connecting ? '正在连接...' : '未连接' }}</p>
      <p v-if="modeInfo" class="mode-info">{{ modeInfo }}</p>
      <el-button v-if="!connecting" type="primary" @click="connect">重新连接</el-button>
    </div>
    <!-- CCTV-style timestamp overlay -->
    <div v-if="connected" class="cctv-timestamp">
      <span>{{ currentTime }}</span>
      <span class="ts-sep">|</span>
      <span>{{ fpsText }}</span>
      <span class="ts-sep">|</span>
      <span>{{ modeBadge }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { VideoCamera } from '@element-plus/icons-vue'
import { getGo2rtcConfig } from '../api'

const props = defineProps<{
  streamName?: string
  lowBandwidth?: boolean
}>()

const videoRef = ref<HTMLVideoElement>()
const containerRef = ref<HTMLDivElement>()
const connected = ref(false)
const connecting = ref(false)
const resolution = ref('')
const mode = ref<'webrtc' | 'mjpeg'>('webrtc')
const modeInfo = ref('')

// --- Clock (date + time, CCTV style) ---
const currentTime = ref('')
let clockTimer: ReturnType<typeof setInterval> | null = null

function updateClock() {
  const now = new Date()
  const y = now.getFullYear()
  const mo = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  const h = String(now.getHours()).padStart(2, '0')
  const mi = String(now.getMinutes()).padStart(2, '0')
  const s = String(now.getSeconds()).padStart(2, '0')
  currentTime.value = `${y}-${mo}-${d} ${h}:${mi}:${s}`
}

// --- FPS ---
const fpsText = ref('')
let frameCount = 0
let fpsTimer: ReturnType<typeof setInterval> | null = null
let rvfcId: number | null = null

function resetFpsCounter() {
  frameCount = 0
}

function startFpsPolling() {
  resetFpsCounter()
  fpsTimer = setInterval(() => {
    fpsText.value = frameCount > 0 ? `${frameCount} fps` : ''
    frameCount = 0
  }, 1000)
}

function bumpFrame() {
  frameCount++
}

function startRvfc() {
  const video = videoRef.value
  if (!video || typeof (video as any).requestVideoFrameCallback !== 'function') return

  function callback() {
    bumpFrame()
    rvfcId = (video as any).requestVideoFrameCallback(callback)
  }
  rvfcId = (video as any).requestVideoFrameCallback(callback)
}

function stopRvfc() {
  if (rvfcId !== null && videoRef.value) {
    (videoRef.value as any).cancelVideoFrameCallback?.(rvfcId)
    rvfcId = null
  }
}

// --- Connection state ---
let pc: RTCPeerConnection | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let webrtcFailed = false

const mjpegUrl = computed(() => '/api/stream.mjpeg?src=camera')

const modeBadge = computed(() => {
  if (mode.value === 'mjpeg') return 'MJPEG'
  return 'H.264'
})

async function connect() {
  if (connecting.value) return

  if (props.lowBandwidth) {
    connectMjpeg()
    return
  }

  if (webrtcFailed) {
    connectMjpeg()
    return
  }

  connecting.value = true
  connected.value = false
  modeInfo.value = ''

  try {
    const { data: config } = await getGo2rtcConfig()
    const name = props.streamName || config.camera_name

    const url = `/api/webrtc?src=${name}`

    pc = new RTCPeerConnection({ iceServers: [] })
    pc.addTransceiver('video', { direction: 'recvonly' })
    pc.addTransceiver('audio', { direction: 'recvonly' })

    pc.ontrack = (event) => {
      if (videoRef.value && event.streams[0]) {
        videoRef.value.srcObject = event.streams[0]
        connected.value = true
        mode.value = 'webrtc'
        startRvfc()
      }
    }

    pc.oniceconnectionstatechange = () => {
      if (!pc) return
      const state = pc.iceConnectionState
      if (state === 'failed' || state === 'disconnected') {
        connected.value = false
        webrtcFailed = true
        disconnect()
        connectMjpeg()
      }
    }

    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/sdp' },
      body: offer.sdp,
    })

    if (!resp.ok) {
      webrtcFailed = true
      disconnect()
      connectMjpeg()
      return
    }

    const answerSdp = await resp.text()
    await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp })
  } catch (e) {
    console.error('WebRTC connect failed:', e)
    webrtcFailed = true
    disconnect()
    connectMjpeg()
  } finally {
    connecting.value = false
  }
}

function connectMjpeg() {
  mode.value = 'mjpeg'
  fpsText.value = '15 fps'
  modeInfo.value = 'MJPEG 直出模式'
  connecting.value = false
  connected.value = false
}

function onMjpegFirstFrame() {
  if (!connected.value) {
    connected.value = true
    resolution.value = '1280x720'
    fpsText.value = '15 fps'
  }
}

function onMjpegError() {
  connected.value = false
  scheduleReconnect()
}

function scheduleReconnect() {
  if (reconnectTimer) clearTimeout(reconnectTimer)
  reconnectTimer = setTimeout(() => {
    disconnect()
    webrtcFailed = false
    connect()
  }, 5000)
}

function disconnect() {
  stopRvfc()
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (fpsTimer) {
    clearInterval(fpsTimer)
    fpsTimer = null
  }
  if (pc) {
    pc.close()
    pc = null
  }
  connected.value = false
  fpsText.value = ''
  frameCount = 0
}

function onVideoReady() {
  if (videoRef.value) {
    const v = videoRef.value
    resolution.value = `${v.videoWidth}x${v.videoHeight}`
  }
}

watch(() => props.lowBandwidth, () => {
  disconnect()
  webrtcFailed = false
  modeInfo.value = ''
  connect()
})

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  startFpsPolling()
  connect()
})

onBeforeUnmount(() => {
  if (clockTimer) clearInterval(clockTimer)
  disconnect()
})

defineExpose({ connect, disconnect, connected })
</script>

<style scoped>
.video-player {
  position: relative;
  width: 100%;
  height: 100%;
  background: #000;
  border-radius: var(--radius);
  overflow: hidden;
  aspect-ratio: 16 / 9;
}

.video-element {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.video-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0.85);
  color: var(--text-secondary);
  gap: 8px;
}

.connecting-icon {
  color: var(--accent);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.mode-info {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* CCTV-style timestamp */
.cctv-timestamp {
  position: absolute;
  bottom: 8px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
  color: #fff;
  font-family: 'SF Mono', 'Cascadia Code', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  font-weight: 500;
  padding: 4px 12px;
  border-radius: 3px;
  line-height: 1.5;
  letter-spacing: 0.3px;
  pointer-events: none;
  z-index: 2;
}
.ts-sep {
  color: rgba(255, 255, 255, 0.3);
}
</style>