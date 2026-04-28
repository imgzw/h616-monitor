import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 10000 })

export interface StorageInfo {
  total_bytes: number
  used_bytes: number
  free_bytes: number
  usage_percent: number
  recordings_bytes: number
  recordings_count: number
}

export interface SystemStatus {
  stream_active: boolean
  recording: {
    is_recording: boolean
    started_at: string | null
    segment_duration: number
    pid: number | null
  }
  storage: StorageInfo
  cpu_temp: {
    temp_c: number
    high_threshold: number
    critical_threshold: number
    warning: boolean
  }
  transcode: {
    available: boolean
    encoder: string
    hw_accelerated: boolean
    v4l2_m2m_available: boolean
    stream_name: string
    low_bandwidth_bitrate: number
  }
  uptime_seconds: number
}

export interface CameraControl {
  name: string
  type: string
  min_val: number
  max_val: number
  step: number
  default_val: number
  current_val: number
  menu_items: Record<number, string> | null
}

export interface RecordingItem {
  filename: string
  path: string
  size_bytes: number
  size_human: string
  created_at: string
  duration: number | null
  thumbnail: string | null
}

export interface RecordingList {
  items: RecordingItem[]
  total: number
  page: number
  page_size: number
}

export interface Go2rtcConfig {
  host: string
  port: number
  camera_name: string
  webrtc_url: string
  mjpeg_url: string
  low_bandwidth_url: {
    available: boolean
    url: string
    protocol: string
    stream_name: string
    encoder: string
    hw_accelerated: boolean
  }
}

export const getStatus = () => api.get<SystemStatus>('/status')
export const getCameraInfo = () => api.get('/camera/info')
export const getControls = () => api.get<CameraControl[]>('/camera/controls')
export const getControl = (name: string) => api.get(`/camera/control/${name}`)
export const setControl = (name: string, value: number) =>
  api.put(`/camera/control/${name}`, { value })
export const zoomIn = (step = 1) => api.post('/camera/zoom/in', null, { params: { step } })
export const zoomOut = (step = 1) => api.post('/camera/zoom/out', null, { params: { step } })
export const zoomSet = (value: number) => api.post('/camera/zoom/set', null, { params: { value } })
export const startRecording = () => api.post('/recordings/start')
export const stopRecording = () => api.post('/recordings/stop')
export const getRecordingStatus = () => api.get('/recordings/status')
export const getRecordings = (page: number, pageSize: number, date?: string) =>
  api.get<RecordingList>('/recordings', { params: { page, page_size: pageSize, date } })
export const deleteRecording = (path: string) => api.delete(`/recordings/${path}`)
export const getDownloadUrl = (path: string) => `/api/recordings/download/${path}`
export const getThumbnailUrl = (path: string) => `/api/recordings/thumbnail/${path}`
export const getStorage = () => api.get('/storage')
export const triggerCleanup = () => api.post('/cleanup')
export const getGo2rtcConfig = () => api.get<Go2rtcConfig>('/go2rtc-config')
export const getStreamUrl = (protocol: string) =>
  api.get('/camera/stream-url', { params: { protocol } })
export const getLowBandwidthUrl = (protocol: string) =>
  api.get('/camera/low-bandwidth-url', { params: { protocol } })

export default api