# Doubao Murmur 本机运维说明

> 本机维护分支：上游 `v1.5.1` + GoatBJH Linux 长期运行修复。

## 当前部署

| 项目 | 值 |
|---|---|
| 源码 | `/data/code/doubao-murmur` |
| GitHub fork | `https://github.com/goatbjh/doubao-murmur` |
| 上游 | `https://github.com/lilong7676/doubao-murmur` |
| Flatpak 应用 | `com.doubao.Murmur`，用户级安装，branch `master` |
| 运行时 | `org.gnome.Platform//49` |
| 自启动 | `~/.config/autostart/com.doubao.Murmur.desktop` |
| 一键重启 | `/data/code/doubao-murmur/linux/restart-flatpak.sh` |
| 日志 | `~/.local/state/doubao-murmur/app.log` |
| 登录凭证 | `~/.config/doubao-murmur/asr_params.json` |

## 本地维护内容

### 长期 CPU 和资源生命周期

- evdev 设备返回 EOF、`ENODEV`、`EIO` 等终止错误后，关闭并删除对应 fd，避免 `select → read → continue` 无等待循环。
- 只监听支持 `EV_KEY` 的输入设备，并每两秒重新枚举，键盘热插拔后无需重启应用。
- ASR WebSocket 正常 EOF 也会清理 `_connected`/`_ws` 并通知录音状态机。
- 每个 ASR 连接线程结束后取消剩余 asyncio task 并关闭 event loop。
- Overlay 动画使用上游已有的 33ms 单一定时器，不再保留本地重复实现。

### 保留的上游 1.5.1 能力

- X11 与 evdev 热键并行工作，兼容 Plasma/GNOME Wayland。
- Wayland 通过 uinput 注入粘贴快捷键，并通过 KWin/xprop 判断终端窗口。
- 普通应用使用 `Ctrl+V`，终端使用 `Ctrl+Shift+V`。
- 停止录音时追加静音并等待结果安静窗口，避免最后一两个字丢失。
- 网络瞬断不会误删登录凭证。

## 构建、安装与重启

仓库位于 `/data`，该目录继承 rslsync ACL。Flatpak Builder 直接在仓库内导出时可能报：

```text
fchown: Invalid argument
```

因此使用主目录中的 build/state 目录：

```bash
rm -rf ~/.cache/doubao-murmur-flatpak-build \
       ~/.cache/doubao-murmur-flatpak-state

flatpak run org.flatpak.Builder \
  --force-clean \
  --user \
  --install \
  --state-dir="$HOME/.cache/doubao-murmur-flatpak-state" \
  "$HOME/.cache/doubao-murmur-flatpak-build" \
  /data/code/doubao-murmur/linux/flatpak/com.doubao.Murmur.yml

/data/code/doubao-murmur/linux/restart-flatpak.sh
```

## 开发测试

```bash
cd /data/code/doubao-murmur/linux
PYTHONPATH=src .venv/bin/python -m pytest tests/ -q
PYTHONPATH=src .venv/bin/python -m compileall -q src
```

重点回归测试：

```text
tests/test_evdev_listener.py  # EOF 忙循环和设备热插拔
tests/test_asr_client.py      # 正常 EOF 和 event loop 清理
```

## 启停与诊断

```bash
# 重启
/data/code/doubao-murmur/linux/restart-flatpak.sh

# 停止
flatpak kill com.doubao.Murmur

# 进程和版本
pgrep -a -f '^python3 -m doubao_murmur$'
flatpak info com.doubao.Murmur

# 日志
tail -n 100 ~/.local/state/doubao-murmur/app.log

# CPU 线程
pid=$(pgrep -n -f '^python3 -m doubao_murmur$')
top -H -p "$pid"
```

如果再次出现高 CPU，先保留进程，不要立即重启，以便抓取具体线程栈。

## 自启动

当前桌面登录通过以下文件启动：

```text
~/.config/autostart/com.doubao.Murmur.desktop
```

对应用户服务通常为：

```text
app-com.doubao.Murmur@autostart.service
```

检查：

```bash
systemctl --user status 'app-com.doubao.Murmur@autostart.service'
```

XFCE/XRDP 会话已通过 `NotShowIn=XFCE;` 排除，避免远程桌面重复启动一份 Murmur。
