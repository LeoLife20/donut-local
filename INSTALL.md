# 从零构建

以下步骤在 macOS 14+ / Apple Silicon 上验证通过（macOS 26.6.2，Xcode CLT 26，Rust stable，Node 24.19，pnpm 12.8）。

## 1. 依赖

```bash
xcode-select --install
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh   # rustup + stable toolchain
# Node 20+（推荐 24），pnpm 12
corepack enable && corepack prepare pnpm@12.8.1 --activate
```

## 2. 取上游并打补丁

```bash
git clone https://github.com/zhom/donutbrowser.git
cd donutbrowser
git checkout 108d731          # v0.33.0 对应的 nightly 提交
git apply /path/to/patches/donut-local.patch
```

补丁包含 133 个文件的改动（本地解锁、字体策略、本地 API、persona 池、车队所需的 Rust 侧改动）。
如果上游已前进到别的提交，`git apply --check` 会报冲突，需要按同一个 tag/commit 取代码。

## 3. 构建

```bash
pnpm install
pnpm build:local
```

产物：`src-tauri/target/release/bundle/macos/Donut Local.app`（约 80 MB，ad-hoc 签名）。

> 首次 `pnpm install` 会下载 Tauri CLI 与 Rust 依赖，约 5–10 分钟；`build:local` 首次编译约 6–10 分钟。

## 4. 首次运行

```bash
open "src-tauri/target/release/bundle/macos/Donut Local.app"
```

- App 会请求下载 Wayfern 引擎（约 1.4 GB），落在
  `~/Library/Application Support/DonutBrowserLocal/binaries/wayfern/<version>/Wayfern.app`。
- 如果从别的机器拷贝了 `.app`，先去掉隔离属性：
  ```bash
  xattr -dr com.apple.quarantine "Donut Local.app"
  ```
- 数据目录：`~/Library/Application Support/DonutBrowserLocal`。

## 5.（可选）移除引擎里的中文字体

```bash
python3 fleet/font/fontscan.py  --fonts "<引擎>/Contents/Frameworks/Wayfern Framework.framework/Versions/<v>/Resources/wayfern_fonts"
python3 fleet/font/strip_fonts.py --fonts "<同样的路径>" \
        --backup "$HOME/wayfern_fonts_backup" --blocklist "$HOME/wayfern_fonts_blocked.txt" --apply
```

移动完字体后必须重新签名，否则引擎启动会失败（sealed resources 校验）：

```bash
codesign --force --sign - "<引擎>/Contents/Frameworks/Wayfern Framework.framework"
codesign --force --sign - "<引擎>"
codesign --verify --deep --strict "<引擎>"
```

字体策略 dylib（枚举层）源码在 `extras/font-policy/`，构建：

```bash
cd extras/font-policy
clang -dynamiclib -O2 -o DonutFontPolicy.dylib font_policy.c -framework CoreText -framework CoreGraphics
```

放到数据目录并由启动器注入 `DYLD_INSERT_LIBRARIES` + `DONUT_FONT_POLICY=latin-only`。
注意：引擎默认带 hardened runtime，`DYLD_INSERT_LIBRARIES` 会被丢弃；注入前需要 ad-hoc 重签。

## 6.（可选）本地 API

本地构建启动后固定监听 `127.0.0.1:10108`，鉴权用固定 loopback token：

```bash
curl -H "Authorization: Bearer local-dev-token" http://127.0.0.1:10108/v1/profiles
```

## 7.（进阶）车队

见 `fleet/README.md`。要点：需要一个已打 local-gate 补丁的 **152** 引擎，
否则引擎会把自定义指纹判为 `withheld`，启动被拒。
