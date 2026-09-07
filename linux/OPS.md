# Doubao Murmur 本机运维说明

> 本机部署记录：Flatpak 用户安装 + 登录自启动 + 识别完成后自动 `Shift+Insert`。  
> 源码：`/sync/code/doubao-murmur`（本地 `v1.4.6`：上游 `v1.4.5` + 粘贴/焦点与长期 CPU 修复）

## 当前状态（2026-07-22）

| 项 | 值 |
|----|----|
| Flatpak 应用 | `com.doubao.Murmur` `1.4.6`（user 安装，branch `master`） |
| 源码目录 | `/sync/code/doubao-murmur` |
| 自启动 | 已开启 |
| 自启动文件 | `~/.config/autostart/com.doubao.Murmur.desktop` |
| 运行时 | `org.gnome.Platform//49` |
| 粘贴快捷键 | 统一 `Shift+Insert`（经 `ydotool` / `wtype` / `xdotool`） |
| 粘贴时序 | 先隐藏悬浮窗/PTT → 等待约 180ms 恢复焦点 → 再注入 `Shift+Insert` |
| 热键 | 右 `Alt` 开始/停止；`ESC` 取消 |
| 一键重启 | `/sync/code/doubao-murmur/linux/restart-flatpak.sh` |
| 运行日志 | `~/.local/state/doubao-murmur/app.log` |
| 登录凭证 | `~/.config/doubao-murmur/asr_params.json` |

配套（已关闭，勿再开）：

- Cherry Studio 自启动：已删除 `~/.config/autostart/cherry-studio.desktop`
- OpenTypeless：已卸载（AppImage / `~/.local/opt/opentypeless` / 自启动项）

## 自启动

### 启用（当前已配置）

文件：`~/.config/autostart/com.doubao.Murmur.desktop`

```desktop
[Desktop Entry]
Name=Doubao Murmur
Name[zh_CN]=豆包语音输入
Comment=Voice-to-text input using Doubao ASR
Comment[zh_CN]=使用豆包语音识别的语音输入工具
Exec=/usr/bin/flatpak run --branch=master --arch=x86_64 --command=doubao-murmur com.doubao.Murmur
Icon=com.doubao.Murmur
Type=Application
Categories=Utility;Accessibility;
StartupNotify=false
Terminal=false
X-KDE-StartupNotify=false
Keywords=voice;speech;asr;input;doubao;
X-Flatpak=com.doubao.Murmur
X-GNOME-Autostart-enabled=true
```

登录桌面会话后会由 `systemd-xdg-autostart-generator` 拉起：

```text
app-com.doubao.Murmur@autostart.service
```

### 关闭自启动

```bash
rm -f ~/.config/autostart/com.doubao.Murmur.desktop
```

### 重新开启自启动

```bash
cat > ~/.config/autostart/com.doubao.Murmur.desktop << 'EOF'
[Desktop Entry]
Name=Doubao Murmur
Name[zh_CN]=豆包语音输入
Comment=Voice-to-text input using Doubao ASR
Comment[zh_CN]=使用豆包语音识别的语音输入工具
Exec=/usr/bin/flatpak run --branch=master --arch=x86_64 --command=doubao-murmur com.doubao.Murmur
Icon=com.doubao.Murmur
Type=Application
Categories=Utility;Accessibility;
StartupNotify=false
Terminal=false
X-KDE-StartupNotify=false
Keywords=voice;speech;asr;input;doubao;
X-Flatpak=com.doubao.Murmur
X-GNOME-Autostart-enabled=true
EOF
chmod 644 ~/.config/autostart/com.doubao.Murmur.desktop
```

## 启停与重启

### 一键重启（推荐）

```bash
/sync/code/doubao-murmur/linux/restart-flatpak.sh
```

行为：

1. `flatpak kill com.doubao.Murmur` 停旧实例  
2. `nohup flatpak run com.doubao.Murmur` 后台启动  
3. 等待进程就绪，日志写入 `~/.local/state/doubao-murmur/app.log`

### 手动

```bash
# 停止
flatpak kill com.doubao.Murmur
pkill -f 'python3 -m doubao_murmur' || true

# 启动
flatpak run com.doubao.Murmur

# 查看是否在跑
flatpak ps --columns=instance,application,pid | rg Murmur
```

## 自动粘贴行为（本地补丁）

### 目标

识别完成后，把结果写入剪贴板，并对**当前输入框**自动发送 `Shift+Insert`。

### 关键改动（相对上游 v1.4.5）

| 文件 | 改动 |
|------|------|
| `linux/src/doubao_murmur/paste/paste_helper.py` | 三条注入路径统一 `Shift+Insert`；去掉终端窗口 `Ctrl+Shift+V` 分支 |
| `linux/src/doubao_murmur/transcription.py` | 完成识别后**先** `_reset_to_idle()` 隐藏 UI，再延迟粘贴 |
| `linux/src/doubao_murmur/config.py` | 新增 `FOCUS_RESTORE_DELAY = 0.18` |
| `linux/tests/test_paste_helper.py` | 同步断言 |
| `linux/restart-flatpak.sh` | 本机一键重启 |

### 为什么需要焦点延迟

Wayland 下录音悬浮窗/PTT 可能占用焦点。若先 `Shift+Insert` 再藏窗，按键会打到 Murmur 自身，目标输入框看起来“没自动输入”。  
实测：快捷键本身 OK、剪贴板也写入了；修好时序后自动输入正常。

### 按键注入依赖

本机（Wayland）：

```bash
systemctl --user is-active ydotool.service   # 期望 active
ls -l /run/user/$(id -u)/.ydotool_socket
id -nG | rg input                           # 用户需在 input 组
```

工具：`ydotool`（优先）、`wtype`、`xdotool`；剪贴板：`wl-copy` / `xclip`。  
Flatpak 内通过 `flatpak-spawn --host` 调宿主工具。

### 成功日志特征

```text
Completing transcription: '……'
Copied to clipboard via wl-copy
Paste simulated via ydotool (Shift+Insert)
```

注意：日志“模拟成功”不等于一定贴进目标框；若仍失败，优先查焦点与 `ydotoold`。

## 从源码重新构建并安装

需要：`org.flatpak.Builder`、`org.gnome.Sdk//49`、`org.gnome.Platform//49`。

```bash
cd /sync/code/doubao-murmur/linux
make flatpak-install
/sync/code/doubao-murmur/linux/restart-flatpak.sh
```

验证运行中的代码是否为补丁版：

```bash
APP=$(flatpak info --show-location com.doubao.Murmur)
rg -n 'FOCUS_RESTORE|110:1|Shift\+Insert' \
  "$APP/files/lib/python/site-packages/doubao_murmur/"{config,transcription,paste/paste_helper}.py

INSTANCE=$(flatpak ps --columns=instance,application | awk '$2=="com.doubao.Murmur"{print $1;exit}')
flatpak enter "$INSTANCE" cat /app/lib/python/site-packages/doubao_murmur/config.py | rg FOCUS_RESTORE
```

开发测试（不改系统 Python）：

```bash
cd /sync/code/doubao-murmur/linux
# 若尚无 .venv：
# /usr/bin/python3 -m venv --system-site-packages .venv
# uv pip install --python .venv/bin/python pytest pytest-asyncio websockets sounddevice python-xlib
PYTHONPATH=src .venv/bin/python -m pytest tests/ -v
```

## 长期 CPU 修复（本地 1.4.6）

- evdev 输入设备返回 EOF/`ENODEV`/`EIO` 后关闭并移除 fd，避免无等待忙循环占满一个 CPU 核心。
- 每两秒重新枚举支持 `EV_KEY` 的输入设备，键盘热插拔后无需重启应用。
- 录音指示器使用约 30 FPS 的单一定时器，不再从绘制回调中无限 `idle_add(queue_draw)`。
- ASR WebSocket 正常 EOF 也会结束连接并通知状态机，避免界面永久卡在 `RECORDING`。
- 每个 ASR 连接结束后关闭对应 asyncio event loop，避免长期使用时积累 selector 资源。

## 常见问题

### 登录后没自启

```bash
ls -la ~/.config/autostart/com.doubao.Murmur.desktop
systemctl --user status 'app-com.doubao.Murmur@autostart.service'
flatpak list --app | rg Murmur
```

### 自动粘贴失效

1. 看日志是否有 `Copied` + `Paste simulated`  
2. 手动 `Shift+Insert` 是否还能贴（能 → 焦点/时序；不能 → 应用不认该快捷键）  
3. 检查 `ydotool.service` 与 socket  
4. 加大 `FOCUS_RESTORE_DELAY` 后重装（见 config.py）

### 强制重新登录豆包

```bash
rm ~/.config/doubao-murmur/asr_params.json
/sync/code/doubao-murmur/linux/restart-flatpak.sh
```

### 完全卸载（含自启动）

```bash
flatpak kill com.doubao.Murmur 2>/dev/null || true
flatpak uninstall --user -y com.doubao.Murmur
rm -f ~/.config/autostart/com.doubao.Murmur.desktop
# 可选：配置与日志
# rm -rf ~/.config/doubao-murmur ~/.var/app/com.doubao.Murmur ~/.local/state/doubao-murmur
```

## 日常使用

1. 光标放在目标输入框  
2. 右 `Alt` 开始说话  
3. 再按右 `Alt` 结束  
4. 约 0.2 秒后文本应通过 `Shift+Insert` 进入输入框  
5. 录音中 `ESC` 取消（不粘贴）

## 相关路径速查

```text
源码          /sync/code/doubao-murmur
运维文档      /sync/code/doubao-murmur/linux/OPS.md
重启脚本      /sync/code/doubao-murmur/linux/restart-flatpak.sh
自启动        ~/.config/autostart/com.doubao.Murmur.desktop
凭证          ~/.config/doubao-murmur/asr_params.json
应用数据      ~/.var/app/com.doubao.Murmur
运行日志      ~/.local/state/doubao-murmur/app.log
```
