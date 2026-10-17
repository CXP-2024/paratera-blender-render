# 无界面 GPU 后处理与传输

已在 2026-10-17 的 RTX 3090 容器上验证 Real-CUGAN 3x 与 RIFE 插帧。角色材质/物理配方属于 genshin-blender-render；本文件补充远端运行和回收中实际遇到的问题。

## 排除软件 Vulkan

EEVEE 的 EGL/OpenGL 已能调用 NVIDIA，并不证明 ncnn Vulkan 已识别到 NVIDIA。若超分程序打印 `llvmpipe (LLVM...)`，它在软件设备上运行；停止本任务对应进程，保存日志，不继续整片。

本次驱动 550.54.14 的 `libGLX_nvidia.so.0` 与 `libnvidia-glvkspirv.so.550.54.14` 已存在，但 NVIDIA Vulkan ICD JSON 缺失。先检查实际驱动和动态库，不盲目安装/替换宿主机驱动。在任务目录创建：

```json
{
  "file_format_version": "1.0.0",
  "ICD": {
    "library_path": "libGLX_nvidia.so.0",
    "api_version": "1.3.277"
  }
}
```

该 API 版本对应本次已测驱动；其他驱动须查匹配能力。仅为任务进程设置 `VK_ICD_FILENAMES=/absolute/job/nvidia_icd.json`，先跑一帧，确认工具打印 `NVIDIA GeForce RTX 3090` 并查看 `nvidia-smi` 的实际利用率/显存，再处理整片。若缺少 NVIDIA 用户态库，先按已有 Blender GPU 环境方法安装与宿主机匹配的库。

`-g 0` 指的是 Vulkan 枚举索引，不自动等于 CUDA GPU 0。仅强制载入 NVIDIA ICD 后，本次它对应唯一的 NVIDIA 设备。不要看到命令里写了 0 就认为实际用了 GPU。

同一 GPU 的超分和神经插帧重任务顺序执行。已验证顺序是 ncnn 子进程结束并释放显存，再载入 PyTorch RIFE。最后 FFmpeg CPU 编码可与轻量数据回收并行，不与另一重渲染抢 GPU。

## 重新启动后的身份和预算

本次既有实例停止再启动后，被分配到不同的物理 GPU UUID。每次都重查实例状态、SSH 登录、GPU UUID、型号、进程与作业锁；不要把旧 UUID 当成当前身份。预算从本次启动请求记时，设置早于总预算的关停余量；只对自己拥有的实例/作业执行停止。

原视频和 PNG 已在持久共享盘时直接复用；只迁移缺少的工具、权重和脚本。优先使用匹配版本的已有资源，记录 SHA-256，不重复上传完整 Blender 包或模型。不要把私有 SSH 缓存、访问密钥、签名下载地址放进公开配方。

## SFTP 分块与有界预读

先前同步 `.read(65536)` 会被往返延迟拖慢。若使用已安装且支持此参数的 Paramiko，可在每一段上有界预读：

```python
remote.seek(start)
remote.prefetch(file_size=end, max_concurrent_requests=8)
left = end - start
while left:
    data = remote.read(min(left, 65536))
    if not data:
        raise EOFError("incomplete segment")
    local_part.write(data)
    left -= len(data)
```

此处 `end` 是该段的绝对结束偏移；预读从 seek 后的当前位置开始。不能给每个分段都预读整个文件。实测以 4 个连接、16 段及每段 8 个预读请求回收 38MB 4K 视频，明显快于同步读取。连接过多会有认证失败；先限制并发、加入有界重试，不用无限加连接解决限速。

只跳过大小完整的旧分段；全部合并到临时文件后校验整体字节数和远端 SHA-256，再原子改名。单独的分段大小并不足以保证传输正确。结果拿回后执行必要的解码/规格检查，用平台 API 停机并确认 `Stopped`；远端程序退出或 GPU 空闲不代表停止计费。
