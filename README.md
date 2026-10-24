# Donut Local（本地版）+ 指纹车队工具

基于 [zhom/donutbrowser](https://github.com/zhom/donutbrowser) **v0.33.0（commit `108d731`）** 的本地构建补丁，外加一套独立于 App 的 profile 工厂/启动器。

> 本项目是 AGPL-3.0 的衍生作品，随附完整源码补丁。**不包含** Donut Browser 或 Wayfern 引擎的任何二进制文件；引擎需由你本机通过 App 首次运行时下载。

---

## 这个包能做什么

| 能力 | 说明 |
|---|---|
| 本地解锁 | 去掉 App 内的 Pro / 套餐 / 试用闸门，profile 数不再受限 |
| 首次下载修复 | 修复首启卡在 “正在下载你的第一个浏览器 0 B” 的问题 |
| 中文字体策略（可选） | 移除 Wayfern 引擎内的 CJK/emoji 字体，并在 macOS 上拦截字体枚举 |
| 本地 API | 固定 loopback token，方便脚本批量建号/启动 |
| 指纹车队（进阶） | 57 个 Apple Silicon 机型 persona、31 个城市/时区/语言、每 profile 独立 canvas/audio 噪声 |

云端能力（备份、团队、远程会话、云调度）仍然由服务端鉴权，本地构建只解锁本机功能。

---

## 目录

```
patches/donut-local.patch          对上游 108d731 的完整补丁（133 个文件）
extras/font-policy/                字体策略 dylib 的 C 源码与构建脚本
extras/engine-gate/                152 引擎的 local-gate 补丁脚本（版本绑定）
fleet/                             车队工具（建号 / 启动 / 测量 / 审计 / persona / 城市表）
docs/REPORT.md                     完整技术报告（含每一步的验证数据）
screenshots/                       运行截图
INSTALL.md                         从零构建步骤
NOTICE.md                          许可与第三方说明
```

---

## 两种用法

**A. 直接用打包好的 App（macOS arm64）**

解压 `DonutLocal-0.33.0-local-arm64.zip`，得到 `Donut Local.app`：

```bash
xattr -dr com.apple.quarantine "Donut Local.app"   # 去隔离，否则 Gatekeeper 拦截
open "Donut Local.app"
```

首次启动会自动下载 Wayfern 引擎（约 1.4 GB）。App 是 ad-hoc 签名，若系统仍拒绝：

```bash
codesign --force --deep --sign - "Donut Local.app"
```

**B. 从源码构建**（需要 Xcode CLT / Rust / Node / pnpm）

见下方「快速开始」。

## 快速开始

```bash
# 1. 取上游代码
git clone https://github.com/zhom/donutbrowser.git
cd donutbrowser
git checkout 108d731

# 2. 打补丁
git apply /path/to/patches/donut-local.patch

# 3. 构建（macOS）
pnpm install
pnpm build:local        # 产物：src-tauri/target/release/bundle/macos/Donut Local.app
```

首次启动会自动下载 Wayfern 引擎（约 1.4 GB）。详细前置依赖见 [INSTALL.md](INSTALL.md)。

---

## 车队工具（可选，进阶）

需要一份 **152.0.7977.64** 的 Wayfern 引擎，并用 `extras/engine-gate/patch_wayfern_local_gate.py` 打上
local-gate 补丁（否则引擎会拒绝自定义指纹，日志为 `dropping N override(s)`）。

```bash
python3 fleet/fleet.py create --count 20          # 建 20 个 profile，自动轮换机型/城市
python3 fleet/fleet.py assign --profile <id> --ip 1.2.3.4   # 按 IP 反查城市/时区/语言
python3 fleet/fleet.py set-proxy --profile <id> --proxy socks5://IP:PORT
node fleet/launch.mjs --profile fleet/profiles/<id>          # 启动并注入噪声
python3 fleet/audit_fleet.py 20                              # 逐台测量，检查唯一性
```

实测（50 台）：canvas 50/50 不同、audio 50/50 不同、机型三元组 50/50 不同、时区与语言零错配。

---

## 已知限制

- 仅测试过 **macOS / Apple Silicon**；Windows 与 Linux 未验证。
- 字体裁剪会改动 App 数据目录里的引擎副本，需要重新签名（脚本已备）；升级引擎后需要重跑。
- 车队走独立启动器，不经过 App 的 profile 管理界面；App 与车队可以共存。
- 无头/自动化接口受引擎自身的能力校验影响，部分 CDP 域会拒绝自动化调用。

---

## 许可

AGPL-3.0（见 `LICENSE`）。上游版权归 Donut Browser 作者所有；本仓库只包含补丁与工具。
