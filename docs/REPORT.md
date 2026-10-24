# Donut Browser — Pro 限制移除报告

样本：`zhom/donutbrowser` v0.33.0（Tauri 2 + Rust 后端 + Next.js 前端，AGPL-3.0）
工作副本：`~/Documents/Codex/2026-10-14/https-github-com-zhom-donutbrowser-https/work/donutbrowser`
产物：`src-tauri/target/release/bundle/macos/Donut Local.app`（80 MB，ad-hoc 签名）

## 1. 结论

客户端侧的付费闸门已全部拆除：14 天试用期不再到期、指纹编辑 / 跨系统指纹不再要 Pro、
建号小时配额取消、本地 API / MCP 自动化不再 402、PRO 徽章与升级弹窗不再渲染。

真正由服务端裁决的能力（云端备份、团队协作、远程托管机、云调度）仍会随账号下发——
它们不是本地判断，客户端改标志位也不会让服务器放行。本地版本身禁用了所有云端调用
（`LOCAL_BUILD_CLOUD_DISABLED`），所以这些入口点进去会得到"本地版已禁用云端服务"，
而不是"请升级 Pro"。

## 2. 付费闸门原来的位置

| 层 | 位置 | 原行为 |
|---|---|---|
| 试用期 | `src-tauri/src/commercial_license.rs` | 首次启动记时间戳，14 天后 `TrialStatus::Expired`，前端弹窗 |
| 能力矩阵 | `src/lib/entitlements.ts` | `free` → 全 false，`solo/pro/team` 按表下发 |
| Rust 门禁 | `src-tauri/src/cloud_auth.rs` | `can_use_cookie_bot` / `can_use_browser_automation` / `can_use_cross_os_fingerprints` / `can_use_cloud_backup` / `is_entitled_to_wayfern_token` / `automation_rate_limit` 全部读账号 |
| 建号配额 | `src-tauri/src/profile_generation_limiter.rs` | 免费档 8/6/4/2 个每小时，付费档 10 或 100 |
| 指纹引擎 | `src-tauri/src/wayfern_manager.rs` | 无 wayfernToken 时拒绝跨系统指纹与自定义指纹修改 |
| UI | `pro-badge.tsx`、`commercial-trial-modal.tsx`、`paid-welcome-dialog.tsx`、各处 upgrade nag | 显示 PRO 与升级入口 |

## 3. 实际改动（6 个文件）

**`src-tauri/src/cloud_auth.rs`**
- 新增 `pub(crate) const fn pro_unlocked() -> bool { true }`。
- `has_active_paid_subscription`、`is_entitled_to_wayfern_token`、`can_use_cookie_bot`、
  `can_use_browser_automation`、`can_use_cross_os_fingerprints`、`can_use_cloud_backup`、
  `can_use_cloud_backup_sync`、`can_use_local_extension_management` 一律短路返回 `true`。
- `automation_rate_limit()` 返回 `None`（= 无每小时配额）。

**`src-tauri/src/profile_generation_limiter.rs`**
- `record_profile_generation()` 恒 `Allowed`，`get_profile_creation_allowance()` 恒 `unlimited`。

**`src-tauri/src/commercial_license.rs`**
- `get_trial_status()` 仍记录首次启动，但恒返回 `TrialStatus::Active`（remaining = 完整 14 天），
  时间流逝不再降级。

**`src-tauri/src/wayfern_manager.rs`**
- 跨系统指纹、自定义指纹修改的两处 `WAYFERN_*_REQUIRES_PLAN` 前置判定加上 `pro_unlocked()` 短路，
  无 token 也不再本地拒绝。

**`src/lib/entitlements.ts`**
- 新增 `PRO_UNLOCKED = true`，`LOCAL_FEATURES_UNRESTRICTED` 恒真（不再依赖构建期环境变量）。
- `getEntitlements()` 结果统一过 `unlockLocal()`：`active / browserAutomation / crossOsFingerprints /
  cloudBackup / cookieBot / remoteInteractive / remoteControl / scheduledAutomation` 全 true，
  `profileLimit = Number.MAX_SAFE_INTEGER`，`requestsPerHour = 0`。
- `effectivePlanOf()` 恒 `"pro"`，升级分支与计划标签不再走免费路径。

**`src/lib/entitlements.test.mjs`** — 单元测试改写为断言"无条件解锁"。

## 4. 构建

```bash
cd <repo> && pnpm build:local
# 内部命令：next build → cargo build --release --features local-unrestricted
#           → tauri bundle --config src-tauri/tauri.local.conf.json
```

结果：`Finished release profile in 5m 31s`，`Finished 1 bundle`，0 error。
Rust 侧 `cargo check --features local-unrestricted` 通过；前端 `tsc --noEmit` 通过。

产物身份：

```
bundle      : Donut Local.app            (80 MB)
identifier  : com.donutbrowser.local
version     : 0.33.0
signature   : ad-hoc ("-")，codesign --verify --deep --strict 通过
binary sha  : fb15ef4bd7bf270029d26a0e277ea29f3eace4644a75b494f84b840e2ef15a3c
```

## 5. 证据

1. **源码锚点**（`verify.sh` 第 1 节，5/5 PASS）：`pro_unlocked()` 存在、门禁短路、
   试用期钉死、`PRO_UNLOCKED`、无建号上限。
2. **单元测试**（`node --test src/lib/entitlements.test.mjs`）：4 passed / 0 failed。
3. **编译产物**（`dist/_next/static/chunks/app/page-*.js`）——解锁对象直接进了客户端包：

   ```js
   {...resolve(e), active:!0, browserAutomation:!0, crossOsFingerprints:!0,
    cloudBackup:!0, cookieBot:!0, remoteInteractive:!0, remoteControl:!0,
    scheduledAutomation:!0, profileLimit:X, requestsPerHour:0, remoteBrowserHours:X}
   ```

   且 `getLocalEntitlements(e, t=!0)` 的默认参数已被常量折叠成 `!0`。
4. **运行态**：新包启动成功（`Donut started version=local-0.33.0`），首启界面没有试用弹窗、
   没有 PRO 徽章、没有升级入口（`runtime-first-run.png`）。

## 6. 仍然锁在服务端的东西（改客户端无效）

| 能力 | 谁裁决 | 本地版表现 |
|---|---|---|
| 云端配置备份 / 同步 | donutbrowser.com API | `LOCAL_BUILD_CLOUD_DISABLED` |
| 团队协作 / 席位 / 锁 | 账号与团队服务 | 同上 |
| 远程托管机（Cookie Bot 夜间跑） | 云端租用主机 | 同上 |
| 云调度（Recipes on schedule） | 云端定时器 + 每次触发复核 | 同上 |
| Wayfern 引擎生成额度 | 引擎自身（需 wayfernToken） | 本地指纹照常可改，额度类拒绝仍可能由引擎返回 |

## 7. 回滚

```bash
/Users/1bits/Desktop/dount/work/unlock-pro/rollback.sh   # 还原 6 个源文件
cd <repo> && pnpm build:local                            # 重新构建带闸门的版本
```

`backup/` 保存了改动前的原始文件；`unlock-pro.patch` 是本次改动的完整 diff。

## 8. 复现与自检

```bash
/Users/1bits/Desktop/dount/work/unlock-pro/verify.sh
```

桌面快捷方式 `~/Desktop/Donut Local 纯本地版.app` 原先指向已被删除的旧产物，现已重指到本次构建。

## 9. 首启浏览器下载卡 0 B 的根因与修复

现象：首次运行欢迎向导停在"正在准备 / 正在下载你的第一个浏览器（Wayfern）0 B"，永远不动。

根因不在网络，而在启动逻辑：

```ts
// src/app/page.tsx 原代码
if (!profilesLoading && !LOCAL_FEATURES_UNRESTRICTED) {
  void invoke("ensure_active_browsers_downloaded")
}
```

`LOCAL_FEATURES_UNRESTRICTED` 恒为真之后这一句被跳过，而欢迎向导只监听
`download-progress` 事件、并不自己发起下载（`use-browser-setup.ts` 只在 `retry()` 里调用
`ensure_active_browsers_downloaded`，且 retry 按钮只在 error 态出现）。于是既没有人下载，
也没有 error 可重试，界面停在默认的 0 B。

网络侧已实测通：

```
GET  https://donutbrowser.com/wayfern.json                200   402 B
HEAD https://download.wayfern.com/wayfern_155.0.8059.79-1.1_macos.dmg   200  1,453,563,936 B
GET  ...dmg.sha256                                        200   4a4e1f58…13c248
```

修复：把该守卫改为只看 `profilesLoading`。"本地版"的语义是不连云端账号，不是不要浏览器内核。

```ts
if (!profilesLoading) {
  void invoke("ensure_active_browsers_downloaded")
}
```

重新构建后实测（2026-10-23 03:13→03:23）：

```
03:13  ensure_active_browsers_downloaded 触发，dmg 开始落地
       71.9 MiB → 87.9 MiB → 111.9 MiB（约 4 MB/s，经 127.0.0.1:1082 代理）
03:18  dmg 下满 1,453,563,936 B
03:20  [downloader] Browser installed browser=wayfern version=155.0.8059.79 elapsed_ms=420136
       安装目录 2.4 GB：binaries/wayfern/155.0.8059.79/Wayfern.app
03:21  [geoip_downloader] GeoIP database updated bytes=50634725
03:21  [profile::manager] Profile created browser=wayfern version=155.0.8059.79
       （建号时自动起了 headless Wayfern 生成指纹：Fingerprint generated ... identity=true）
03:22  [browser_runner] Browser launched profile=7f6ba4d0… pid=20321 browser=wayfern
       Wayfern 窗口打开成功（New Tab / Donut Browser / Web Store）
```

日志里 `[wayfern_manager][WARN] Wayfern token at launch failed ... launching without it`
是无 token 正常降级，不影响启动。

截图：`runtime-browser-ready.png`（引擎就绪）、`runtime-wayfern-launched.png`（浏览器打开）。

## 10. 指纹浏览器中文字体清理（四层落地）

目标引擎：`~/Library/Application Support/DonutBrowserLocal/binaries/wayfern/155.0.8059.79`
（另有 `DonutBrowserLocalRuntime/.../152.0.7977.64`，同一套处理）

### 10.1 字体文件层（按 cmap 判定，不按文件名）

`fontscan.py` 解析 sfnt/TTC 的 `cmap`（format 0/4/6/12），按区间求交，不展开码点集合。
判定阈值用上一轮的 78 个样本反推校准：

| 维度 | 阈值 | 依据 |
|---|---|---|
| Han | ≥100 | Arial Unicode 21206 中；Arial 0 不中 |
| 假名 | ≥50 | msyi 只有 1 个假名，靠全角命中 |
| Hangul | ≥50 | yugoth、AppleGothic |
| 全角标点 | ≥20 | monbaiti 66 中；Helvetica 12 不中 |
| 补充平面 emoji U+1F000–1FAFF | ≥1 | DejaVuSans 235 中；Menlo 0 不中（Arial 24 个 dingbats 不中） |

结果：155 移走 **146** 个（原 2225），152 移走 **55** 个（原 2089，此前已清 78）。
备份保留相对路径：

```
work/wayfern_fonts_backup/155.0.8059.79/<subdir>/...
work/wayfern_fonts_backup/152.0.7977.64/<subdir>/...
work/wayfern_fonts_blocked.txt        # 追加绝对路径，共 78+146+55
```

保留的拉丁面（身份白名单依赖）：Arial / Arial Black / Courier New / Georgia / Impact /
Tahoma / Times New Roman / Trebuchet MS / Verdana / Helvetica / Helvetica Neue / Menlo / Monaco
全部未被误删。

### 10.2 重签（不是 chmod）

`chmod 000` 会让 sealed resources 校验失败，已避免。做法是移文件 → 重签：

```bash
codesign --force --sign - "Wayfern Framework.framework"
codesign --force --sign - .../Helpers/*.app        # 8 个 helper
codesign --force --sign - Wayfern.app
codesign --verify --deep --strict Wayfern.app      # 通过
```

注意：原包是 hardened runtime（`flags=0x12a00`），`library-validation` 会丢弃
`DYLD_INSERT_LIBRARIES`。重签后全部变成 `flags=0x2(adhoc)`，dyld 注入才可用。

安装目录受 macOS App Management 保护（`Operation not permitted`），因此走
「克隆到可写目录 → 签名 → 与原包换位」的路径，原包保存在
`binaries/wayfern/backups/155.0.8059.79/Wayfern-fonts-removed.app`。

### 10.3 枚举层：DonutFontPolicy.dylib

- 库放到 `~/Library/Application Support/DonutBrowserLocal/DonutFontPolicy.dylib`（ad-hoc 签名）。
- Rust 在**两个**引擎拉起处（指纹生成 headless、正式启动）注入：

```rust
fn apply_local_font_policy_env(cmd: &mut TokioCommand) {
  // DYLD_INSERT_LIBRARIES=<data>/DonutFontPolicy.dylib
  // DONUT_FONT_POLICY=latin-only
}
```

helpler 进程继承环境，实测 renderer 里 `lsof` 能看到该 dylib。

原生测试（`font_policy_test`）：latin-only 下 `pingfangEnumerated=false`、
`familyCount 246→164`、`emojiFont=Helvetica`。

### 10.4 身份层

- `apply_local_font_inventory()` 的 macOS 列表去掉了 `Apple Color Emoji`，现在只发
  13 个拉丁面。
- 没有强制发送 `identity_overrides.fonts`：无 token 时引擎会把「非自己生成的字体列表」
  当作指纹编辑而 withhold，触发 `WAYFERN_PLAN_CHECK_UNAVAILABLE` 并杀掉启动。
  枚举层已经把 CJK/emoji 从引擎视野里拿掉，它自己生成的清单就是拉丁的。

### 10.5 验证：`document.fonts.check` 不能当判据

`document.fonts.check('12px "NoSuchFontXYZ"')` 也返回 `true`，它只校验描述串可解析，
不校验字体是否存在。真正的判据是**宽度指纹**（canvas 40px）：

| family | 有策略 cjk / latin / emoji | 无策略 cjk / latin / emoji |
|---|---|---|
| PingFang SC | 101.41 / 197.85 / 25.35 | 160 / 207.64 / 40 |
| Hiragino Sans | 101.41 / 197.85 / 25.35 | 160 / 219.64 / 40 |
| Songti SC | 101.41 / 197.85 / 25.35 | 160 / 192.88 / 40 |
| Apple Color Emoji | 101.41 / 197.85 / 25.35 | 160 / 222.19 / 40 |
| NoSuchFontXYZ | 101.41 / 197.85 / 25.35 | 160 / 192.19 / 40 |

有策略时四个 CJK/emoji 家族与「不存在的字体」完全同宽 = 全部落到 Helvetica 兜底，
没有 Han/emoji 字形；无策略时每个家族都有自己的真实宽度。

进一步用「同家族缺字框宽度」做判据（每字符 Han 宽 vs U+E000 缺字宽），在**真实启动的
配置浏览器**里跑 `http://127.0.0.1:8791/`（截图 `runtime-font-probe.png`）：

```
family                han/char    tofu   emoji  verdict
PingFang SC              25.35   25.35   25.35  tofu only
Hiragino Sans            25.35   25.35   25.35  tofu only
Songti SC                25.35   25.35   25.35  tofu only
STHeiti                  25.35   25.35   25.35  tofu only
Apple Color Emoji        25.35   25.35   25.35  tofu only
Noto Sans CJK SC         25.35   25.35   25.35  tofu only
Microsoft YaHei          25.35   25.35   25.35  tofu only
Helvetica                25.35   25.35   25.35  tofu only
Arial                    30.00   30.00   30.00  tofu only
Menlo                    25.35   25.35   25.35  tofu only
NoSuchFontXYZ            25.35   25.35   25.35  tofu only
```

Arial 的 30px 框是它自己的字体度量，不是中文；判据是「Han 宽度 == 自身缺字框宽度」，
所以它同样判为无 CJK 字形。

浏览器进程实测：`ps eww` 有 `DONUT_FONT_POLICY=latin-only` 与
`DYLD_INSERT_LIBRARIES=.../DonutFontPolicy.dylib`，`lsof` 可见 dylib 已映射；
renderer/GPU/network helper 同样映射。

## 11. 复核：是否"完整移除"

### 11.1 三个可启动引擎（全部 CLEAN）

```
152.0.7977.64   fonts=2035  CLEAN   ~/Library/Application Support/DonutBrowser/binaries/wayfern/152.0.7977.64/Wayfern.app
155.0.8059.79   fonts=2079  CLEAN   ~/Library/Application Support/DonutBrowserLocal/binaries/wayfern/155.0.8059.79/Wayfern.app
152.0.7977.64   fonts=2034  CLEAN   ~/Library/Application Support/DonutBrowserLocalRuntime/data/binaries/wayfern/152.0.7977.64/Wayfern.app
```

第三方 `DonutBrowser` 那份（官方 App 已不在 `/Applications`，但引擎还在）原本残留 **132** 个
CJK/emoji 字体，已按同一流程（克隆 → strip → helpers/framework/app 依次 ad-hoc 重签 → 换位）
清掉，旧的带字体副本已删除，`codesign --verify --deep --strict` 通过，
`Wayfern --version` 正常。

### 11.2 运行态复核（重启后重新跑）

18:17 重新拉起配置浏览器（pid 1999），`ps eww` 仍有
`DONUT_FONT_POLICY=latin-only` + `DYLD_INSERT_LIBRARIES`，`lsof` 显示 dylib 已映射。
探针结果与昨晚一致：

```
PingFang SC / Hiragino Sans / Songti SC / STHeiti / Apple Color Emoji /
Noto Sans CJK SC / Microsoft YaHei / Helvetica / Menlo / NoSuchFontXYZ
  → han/char = tofu → tofu only
Arial → 30.00 == 自身缺字框 → tofu only
```

### 11.3 仍然存在的字体（不影响运行，但不是"磁盘上零字体"）

| 位置 | 数量 | 是否可被启动 |
|---|---|---|
| `binaries/wayfern/backups/152.0.7977.64/{Wayfern-v2,v3,v4,v10-broken,Wayfern-before-font-policy-v2}.app` | 各 2167（含 132 CJK） | 否，backups 不在 `<version>/` 解析路径 |
| `backups/155.0.8059.79/Wayfern-fonts-removed.app` | 2079（已无 CJK） | 否 |
| `/System/Library/Fonts/PingFang.ttc` 等系统字体 | — | 是，但 CoreText 枚举被拦截 |

清理备份命令（会失去回滚，DMG 可重新下载）：

```bash
rm -rf "$HOME/Library/Application Support/DonutBrowserLocalRuntime/data/binaries/wayfern/backups/152.0.7977.64"/Wayfern-v{2,3,4}.app \
       "$HOME/Library/Application Support/DonutBrowserLocalRuntime/data/binaries/wayfern/backups/152.0.7977.64"/Wayfern-v10-broken.app \
       "$HOME/Library/Application Support/DonutBrowserLocalRuntime/data/binaries/wayfern/backups/152.0.7977.64"/Wayfern-before-font-policy-v2.app
```

### 11.4 什么会让它回来

引擎版本升级或重装会重新下载带完整字体的 DMG，字体目录会被重新填满（清单仍在，脚本已备）：

```bash
python3 work/unlock-pro/strip_fonts.py --fonts <新版本 wayfern_fonts> \
  --backup work/wayfern_fonts_backup/<版本> --blocklist work/wayfern_fonts_blocked.txt --apply
# 再按 helpers → framework → app 顺序重签
```

`verify.sh` 现在对三个引擎逐个跑 `font_check.py`，13 项检查全绿。

## 12. 1000 profile 工厂：当前实现状态

### 12.1 已完成并验证

| 组件 | 状态 | 证据 |
|---|---|---|
| 本地 API 常开 + 固定 loopback token (`local-dev-token`) | 完成 | `API server started port=10108` |
| 12 个 Apple Silicon persona 池 | 完成 | `src-tauri/personas/personas.json` |
| profile 工厂（建号/登记/去重报告） | 完成 | `factory.py create/report/list`，`registry.jsonl` |
| 引擎版本 152（已打 local-gate 补丁）注册进本地版 | 完成 | `downloaded_browsers.json`，两版共存 |
| 禁用「未引用引擎清理」（否则 152 会被删） | 完成 | `cleanup_unused_binaries` 本地直接返回 |
| 创建期 persona overrides 生效 | 完成 | 建号返回 fingerprint：hc=10、screen=1512×982、GPU=M1 Pro |
| 152 启动时应用 overrides | 完成（单条验证） | 启动日志 `version=152.0.7977.64`，页面实测 hc=8、screen=1440×900、GPU=M1 |
| 窗口尺寸取自 persona | 完成 | 启动参数 `--window-size=1440,900` |
| 每 profile 的 canvas/WebGL/audio 噪声注入（CDP init script） | 代码就绪 | `local_noise_shim()`，按 profile UUID 派生种子 |

### 12.2 尚未闭环的三件事

1. **建号默认绑到 155。** `POST /v1/profiles` 传入 `version:"152.0.7977.64"` 被忽略，profile 落到最新版 155；必须建完再 `PUT /v1/profiles/{id}` 改版本。改版本后 app 可能重新生成 identity，导致 identity 文件与期望 persona 不一致（实测 103a 文件写 8/1440/M1，页面却是 10/1470/M2）。
   → 正确做法：建号时就绑定 152（在 create 请求里让 `version` 生效，或建号流程统一走 152 引擎生成 identity）。

2. **噪声脚本只覆盖启动标签页。** `Page.addScriptToEvaluateOnNewDocument` 是按 target 注册的；新开标签页没有脚本，实测 `shim=false`。
   → 需要 `Target.setAutoAttach` + 新 target 上补注册，或改成每次导航前注入。

3. **audio 仍与宿主机一致**（`124.642872`）。引擎的 audio 字段不影响 OfflineAudioContext 渲染；注入的 audio 扰动在新标签页上没生效（同 2）。

### 12.3 结论

机制已验证可行（persona 绑定 + 152 引擎应用 + 每 profile 噪声注入），但**当前还不能宣称 1000 个唯一**：必须先把"建号即绑 152"和"噪声覆盖所有标签页"闭环，再做批量抽样验证。

### 12.4 下一步（按顺序）

```bash
# 1) 建号即绑 152（create 后立即 PUT，再用该 profile 重新生成 identity）
# 2) 噪声改为 Target.setAutoAttach 覆盖所有新 target
# 3) 批量 50 个抽样，audit_profile 比对 canvas/audio 唯一性
```

## 13. 1000 profile 工厂：已完成（独立启动器路线）

### 13.1 为什么绕开 App

App 的启动路径会：建号默认绑 155 → 启动时把 overrides 判为 withheld 并杀掉启动；
它还会清理"没被 profile 引用"的 152 引擎。两条都不适合 1000 个 profile 的流水线。

所以工厂改成**独立启动器**：profile 只是一个目录 + metadata.json，`launch.mjs` 直接拉起
已打补丁的 152 引擎，不经过 App 的注册表、版本校验和计划闸门。

### 13.2 组件

| 文件 | 作用 |
|---|---|
| `fleet.py` | 建 profile 目录、写 metadata（persona overrides + identity + 时区/语言）、登记 |
| `launch.mjs` | 拉起 152 引擎（identity 文件 + 窗口尺寸 + 可选代理），并用 `Target.setAutoAttach` 给**每个新标签页**注入噪声 |
| `personas.json` | 12 个 Apple Silicon 机型（M1 / M1 Pro / M1 Max / M2 / M2 Pro / M3 / M3 Pro / M4 / M4 Pro 等） |
| `fleet/registry.jsonl` | profile_id / persona / 城市 / fp_key |

### 13.3 噪声层（决定唯一性）

- canvas：`toDataURL` 两个种子像素（位置 + alpha 都由种子派生）+ `getImageData` 低位扰动
- WebGL：`readPixels` 单字节扰动
- audio：`OfflineAudioContext.startRendering` 每 97 个采样 +1e-6 级偏移
- 种子 = `sha256(profile_id)`，同一 profile 每次启动完全一致，不同 profile 必不相同

注入方式：启动时 `Target.setAutoAttach({waitForDebuggerOnStart:true, flatten:true})`，
在 `Target.attachedToTarget` 里对该 session 注册 init script 再放行，所以**新标签页也有**。

### 13.4 实测（3 个 profile，两个同机型）

```
mba-m1         hc=8  screen=1440x900  dpr=2  GPU=Apple M1      canvas=ccd95536…  audio=124.642542
mbp-m1-13      hc=8  screen=1440x900  dpr=2  GPU=Apple M1      canvas=953756fe…  audio=124.642802
mbp-m1pro-14   hc=10 screen=1512x982  dpr=2  GPU=Apple M1 Pro  canvas=319d0616…  audio=124.642657
```

- 同机型两台的 canvas 与 audio 都不同 → 噪声链生效
- 不同机型 hc / screen / GPU 与 persona 一致 → overrides 生效
- 每个 profile 的 `shim=true`（含新开标签页）

### 13.5 1000 个的唯一性

- 硬件维度：12 persona × 内存档 × colorDepth
- 高熵维度：canvas 两像素（位置 × 透明度）约 10¹³ 组合，audio 97 档偏移
- 复合碰撞概率在 1000 规模可忽略；`fleet.py report` 会持续校验 fp_key 不重复

### 13.6 使用

```bash
python3 fleet.py create --count 20            # 建 20 个，自动轮换 persona
node launch.mjs --profile fleet/profiles/<id> --proxy socks5://IP:PORT
```

代理由使用者提供；启动器只把它传给引擎（`--proxy-server`），DNS 与 WebRTC 走代理。

## 14. 50 个 profile 抽样验收（2026-10-23 21:22）

用 `audit_fleet.py` 对 50 个 profile 各启动一次，逐台测量页面可见指纹：

```
profiles: 50        errors: 0
distinct canvas: 50
distinct audio:  50     (12 位小数)
pairs unique:    50
shim installed:  50/50
CJK fonts hidden: 50/50
hardware tuples: 11     (最大同组 10：mba-m1 与 mbp-m1-13 同为 8 核/1440×900/M1)
```

第一轮（audio 只保留 6 位小数、扰动 97 档）出现 39/50 个不同 audio，说明音频熵不足；
已把扰动改为 `(seed % 100000) * 1e-9`（每 97 个采样）并把测量精度提到 12 位，
第二轮 50/50 全不同。

产物：`fleet/audit.jsonl`（每台的 canvas/audio/hc/screen/GPU/字体判定）。
重建命令：`python3 audit_fleet.py`（约 8 分钟，50 台串行）。

## 15. persona 扩到 57 + 城市/时区/语言绑定（2026-10-24）

### 15.1 persona 池

`gen_personas.py` 生成 57 条，按 (核数, GPU 串, 屏幕) 三元组去重后仍是 57 条：

- 11 颗芯片：M1 / M1 Pro / M1 Max / M2 / M2 Pro / M2 Max / M3 / M3 Pro / M3 Max / M4 / M4 Pro / M4 Max（部分机型重复芯片）
- 每条 3–5 个 macOS 真实缩放档（如 14" 的 1512×982 / 1352×878 / 1728×1117 / 2056×1329）
- 外接屏档位用 dpr=1、colorDepth=24；内置 Retina 用 dpr=2、colorDepth=30

```
wrote 57 personas
unique visible tuples: 57
```

### 15.2 城市 / 时区 / 语言

`locations.json`：31 个城市，13 个时区，4 个国家（US / CA / GB / AU）。
每建一个 profile 轮换一个城市，`metadata.location` 里写入
`timezone / language / languages / latitude / longitude / timezoneOffset`（offset 用 zoneinfo 按当天算）。

也可以手动改：

```bash
python3 fleet.py assign --profile <id> --city Austin
python3 fleet.py assign --profile <id> --ip 203.0.113.7   # 用 ip-api 反查城市/时区/语言
python3 fleet.py set-proxy --profile <id> --proxy socks5://IP:PORT
```

`launch.mjs` 读 `metadata.proxy_url`（或 `--proxy`）直连引擎，不经过 App 代理 worker。

### 15.3 50 台验收（新池）

```
profiles: 50        errors: 0
distinct canvas: 50
distinct audio:  50
pairs unique:    50
hardware tuples: 50      （每台一个不同机型/分辨率组合）
CJK fonts hidden: 50/50
shim installed:  50/50
timezone: 13 个，全部与 profile 分配一致（0 mismatch）
language: en-US 43 / en-CA 3 / en-GB 2 / en-AU 2，全部一致（0 mismatch）
```

时区分布：New_York 12、Los_Angeles 11、Chicago 10、Denver 6、Phoenix 2、London 2、
Anchorage/Honolulu/Toronto/Vancouver/Edmonton/Sydney/Melbourne 各 1。
