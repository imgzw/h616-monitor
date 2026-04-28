# H616 监控平台

基于全志H616 (Armbian) 的USB摄像头监控平台，支持WebRTC超低延迟实时预览、循环录制、远程变焦控制。

## 架构

```
USB Camera → go2rtc (WebRTC/MJPEG流媒体)
                 ├→ 浏览器实时预览 (<500ms延迟)
                 ├→ ffmpeg 分段录制 (5分钟MP4切片)
                 └→ V4L2 变焦控制
```

| 组件 | 技术 | 作用 |
|------|------|------|
| 流媒体 | go2rtc | WebRTC/MJPEG推流，极低延迟 |
| 录制 | ffmpeg | MJPEG→MP4分段录制，零转码 |
| 后端 | Python FastAPI | API、摄像头控制、磁盘管理 |
| 前端 | Vue3 + Element Plus | 深色主题监控界面 |
| 进程管理 | systemd | 自动重启、看门狗 |

## 快速部署

### 1. 在开发机构建前端

```bash
cd frontend
npm ci
npm run build
```

### 2. 在H616上一键安装

```bash
scp -r h616/ root@h616-ip:/tmp/h616-monitor
ssh root@h616-ip
cd /tmp/h616-monitor
sudo bash deploy/install.sh
```

### 3. 手动安装 (可选)

```bash
# 安装依赖
sudo apt install python3 python3-pip python3-venv ffmpeg v4l-utils nginx

# 安装 go2rtc
sudo wget -O /usr/local/bin/go2rtc https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_arm64
sudo chmod +x /usr/local/bin/go2rtc

# 配置
sudo cp config/go2rtc.yaml /opt/h616-monitor/config/
sudo cp deploy/go2rtc.service /etc/systemd/system/
sudo cp deploy/h616-monitor.service /etc/systemd/system/
sudo cp deploy/nginx.conf /etc/nginx/sites-available/h616-monitor
sudo ln -s /etc/nginx/sites-available/h616-monitor /etc/nginx/sites-enabled/

# 后端
cd /opt/h616-monitor/backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 启动
sudo systemctl daemon-reload
sudo systemctl enable go2rtc h616-monitor nginx
sudo systemctl start go2rtc
sudo systemctl start h616-monitor
sudo systemctl restart nginx
```

## 配置

### 环境变量 (后端)

| 变量 | 默认值 | 说明 |
|------|--------|------|
| H616_CAMERA_DEVICE | /dev/video0 | 摄像头设备路径 |
| H616_RECORDINGS_DIR | /opt/h616-monitor/recordings | 录像存储路径 |
| H616_SEGMENT_DURATION | 300 | 分段时长(秒) |
| H616_DISK_HIGH_THRESHOLD | 0.80 | 磁盘使用率清理阈值 |
| H616_DISK_LOW_THRESHOLD | 0.70 | 清理目标使用率 |
| H616_GO2RTC_HOST | 127.0.0.1 | go2rtc地址 |
| H616_GO2RTC_PORT | 1984 | go2rtc端口 |

### go2rtc 配置

编辑 `/opt/h616-monitor/config/go2rtc.yaml`:

```yaml
streams:
  camera:
    - "video /dev/video0"
```

## API

| 路径 | 方法 | 说明 |
|------|------|------|
| /api/status | GET | 系统状态 |
| /api/camera/info | GET | 摄像头信息 |
| /api/camera/controls | GET | 可用控制列表 |
| /api/camera/control/{name} | PUT | 设置控制值 |
| /api/camera/zoom/in | POST | 变焦放大 |
| /api/camera/zoom/out | POST | 变焦缩小 |
| /api/camera/zoom/set | POST | 设置变焦值 |
| /api/recordings/start | POST | 开始录制 |
| /api/recordings/stop | POST | 停止录制 |
| /api/recordings | GET | 录像列表 |
| /api/recordings/{path} | DELETE | 删除录像 |
| /api/recordings/download/{path} | GET | 下载录像 |
| /api/recordings/thumbnail/{path} | GET | 缩略图 |
| /api/storage | GET | 存储信息 |
| /api/cleanup | POST | 手动触发清理 |

## 稳定性设计

- systemd 自动重启 (Restart=always, 3秒重启)
- WatchdogSec=30 看门狗
- ffmpeg 进程守护 (崩溃自动重启)
- 磁盘自动清理 (超过80%自动删除最旧录像至70%)
- WebRTC 自动重连
- uvicorn 单worker避免资源竞争

## 故障排查

```bash
# 检查服务状态
systemctl status go2rtc h616-monitor nginx

# 查看日志
journalctl -u go2rtc -f
journalctl -u h616-monitor -f

# 检查摄像头
v4l2-ctl --list-devices
v4l2-ctl --device=/dev/video0 --list-ctrls

# 测试go2rtc
curl http://localhost:1984/api/streams
```