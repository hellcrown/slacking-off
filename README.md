# 摸鱼哨兵（Sentinel）

用摄像头做人脸监测：当画面里出现**第二个人**（人数达到阈值）时，自动执行你预设的动作——
关闭某个程序、最小化窗口、把摸鱼窗口压到最底层、瞬间把"工作窗口"切到最前、执行任意命令。
人走开后还能自动恢复。全部检测在本地完成，**不上传任何画面**。

## 快速开始

**方式一（推荐给其他电脑使用）：** 直接双击 `dist\MoyuSentinel.exe`，无需安装 Python。
单文件版首次启动需解压，可能要十几秒（杀毒软件扫描），之后稳定在 4 秒左右，属正常现象。

**方式二（源码运行）：** 双击 `start.bat`，或：

```
E:\anaconda\anaconda\python.exe main.py
```

程序启动后常驻系统托盘（图标颜色：灰=未监测，绿=监测中，红=已触发）。

### exe 版本说明

- 配置文件 `config.json` 生成在 exe 同目录，删除它即恢复默认设置
- 出问题时看 exe 同目录的 `sentinel.log`（源码模式日志在控制台）
- 部分杀毒软件对 PyInstaller 打包的程序容易误报，若被拦截请加白名单
- 重新打包：`E:\anaconda\anaconda\python.exe -m PyInstaller --clean --noconfirm sentinel.spec`
  （需已安装 `pyinstaller`）

## 依赖（源码方式运行）

运行环境为 Anaconda base（Python 3.11）。所需库：`opencv-python`、`PyQt5`、`pywin32`、`psutil`、`numpy`。
缺什么就装什么：

```
E:\anaconda\anaconda\python.exe -m pip install -r requirements.txt
```

人脸模型 `models/face_detection_yunet_2023mar.onnx`（232KB，来自官方 opencv_zoo）已随项目附带，
无需联网。

## 使用说明

1. **设置动作**：主窗口 → 设置 → "触发动作"表格。
   添加动作，选择类型，填写目标；点"从当前窗口选择目标…"可直接从当前打开的窗口里点选。
   - 目标按**标题模糊匹配**（不区分大小写，包含即匹配）。建议填稳定的关键词，
     例如浏览器窗口标题会随标签页变化，填更靠得住的词（如"网易云音乐"）。
   - "人走后恢复"仅对可逆动作（最小化/压底）有效；关程序、执行命令、置前不可逆。
2. **检测参数**（都有悬停提示）：
   - 触发人数阈值：默认 2（出现第二张脸才触发）。设为 1 = 摄像头里出现任何人就触发
     （适合把摄像头对准门口）。
   - 连续确认帧数：默认 8 帧（约 0.3~0.5 秒）。需要连续这么多帧都达标才触发，
     防止海报、玩偶、瞬时误检引发误动作。误报多就调大；反应慢就调小。
   - 检测灵敏度阈值：0.5 敏感 ~ 0.9 严格，默认 0.6。
   - 最小人脸尺寸：过滤画面里太小的可疑"人脸"，默认 80 像素。
   - 触发冷却（秒）：触发后这段时间内不重复触发。
   - 恢复确认帧数：人数回落并保持这么多帧后执行恢复。
3. **热键**（可在设置中修改，需含 Ctrl/Alt/Shift 修饰键）：
   - `Ctrl+Alt+S`：开始/停止监测
   - `Ctrl+Alt+H`：老板键——不管监测状态，立即执行全部动作
   - 默认组合已避开常见占用（如 Ctrl+Alt+M/F 在部分机器被其他软件占用）；
     若注册失败，主窗口日志会提示，换一个组合即可。
4. **托盘菜单**：开始/停止监测、立即执行动作、显示主窗口、退出。
   点窗口右上角 × 只是隐藏到托盘，真正退出请走托盘菜单。
5. 所有设置保存在 `config.json`，重启后依然生效。

## 触发逻辑说明

```
摄像头(640x480) → YuNet 人脸检测(每帧) → 人数 >= 阈值 连续 N 帧
      → 执行动作（冷却 X 秒）→ 人数 < 阈值 连续 M 帧 → 自动恢复
```

## 已知限制

- 前置摄像头拍"身后探头的人"，看到的主要是人脸，因此以**人脸检测**为主，
  不做人体检测（该场景不可靠）。
- 使用期间摄像头指示灯常亮（正在采集）。
- 光线过暗时检出率下降：可调低"检测灵敏度阈值"与"最小人脸尺寸"。
- 检测在本机 CPU 上运行（实测约 13ms/帧，占用很低）。

## 故障排查

- **点了"开始监测"没反应**：程序会弹窗显示具体原因（旧版本只写日志，请更新到新版）。
  详见 exe 旁的 `sentinel.log`。
- **摄像头打不开 / 提示无画面**：
  1. 设置里点"**测试摄像头**"，自动探测 0-3 号哪个能用；
  2. 检查是否被其他程序占用（微信视频、腾讯会议、直播/美颜软件）；
  3. Windows 设置 → 隐私和安全性 → 摄像头 → 打开"允许桌面应用访问摄像头"；
  4. 笔记本 Fn 摄像头开关或物理滑盖；
  5. 设备管理器 → 照相机 → 看设备是否带感叹号；
  6. 本机曾因 **360 摄像头防护残留的注册表过滤器**导致所有摄像头报"代码 19"。
     修复方法（管理员 PowerShell）：备份并删除
     `HKLM\SYSTEM\CurrentControlSet\Control\Class\{ca3e7ab9-b4c3-4ae6-8251-579ef933890f}`
     中 `UpperFilters` 里的 `360Camera` 项（保留 `ksthunk`），再重启设备。
     参考脚本见 `tools/fix_camera2.ps1`。
- **热键注册失败**：说明被其他软件占用，换一个组合。
- **动作没执行**：查看主窗口日志；最常见原因是目标关键词没有匹配到任何窗口标题
  （标题会变化，用设置里的"从当前窗口选择目标"重新选一次）。

### 兼容性说明

- 人脸模型通过**内存加载**，中文 Windows 用户名（如 `C:\Users\陈帅父亲\...`）、
  中文安装路径均可正常运行（v1.1 修复：旧版在中文用户名机器上会因临时目录
  路径含中文而启动监测失败）。
- 仅支持 Windows 10/11。

## 项目结构

```
main.py                 入口：窗口 + 托盘 + 热键
sentinel.spec           PyInstaller 打包配置
core/config.py          配置与持久化(config.json)
core/detector.py        YuNet 人脸检测
core/monitor.py         监控线程与触发状态机
core/actions.py         动作执行器（窗口/进程操作与恢复）
ui/main_window.py       主窗口
ui/settings_dialog.py   设置对话框
ui/window_picker.py     窗口选择器
models/                 人脸模型
assets/                 程序图标
tools/                  一次性修复脚本（摄像头）
tests/                  集成测试（动作链路、端到端触发、exe 验收）
```

## 测试

```
E:\anaconda\anaconda\python.exe tests\test_actions.py        # 窗口/进程动作全链路
E:\anaconda\anaconda\python.exe tests\test_integration.py    # 摄像头->触发->恢复端到端
E:\anaconda\anaconda\python.exe tests\test_app_real.py       # 真实 GUI 应用验证
E:\anaconda\anaconda\python.exe tests\test_settings_ok.py    # 设置保存回归
E:\anaconda\anaconda\python.exe tests\test_unicode_paths.py  # 中文用户名/路径回归
E:\anaconda\anaconda\python.exe tests\test_exe.py            # exe 验收（需先打包）
```
