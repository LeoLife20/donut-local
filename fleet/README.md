# 车队工具（进阶）

这套工具不经过 App 的 profile 管理，直接创建 profile 目录并拉起引擎。适合几十到上千个
预生成 profile、每次只开几台的场景。

## 前置条件

1. 一份 **152.0.7977.64** 的 Wayfern 引擎（`Wayfern.app`）。
2. 用 `extras/engine-gate/patch_wayfern_local_gate.py` 给它打 local-gate 补丁：
   ```bash
   python3 extras/engine-gate/patch_wayfern_local_gate.py --app "/path/Wayfern.app" --profile local-all
   ```
   该脚本按版本与原始哈希校验，只改本机副本，不触碰服务端校验。
3. 记下引擎路径，启动时用 `WAYFERN_APP` 指过去（默认指向
   `~/Library/Application Support/DonutBrowserLocalRuntime/data/binaries/wayfern/152.0.7977.64/Wayfern.app`）。

> 不打补丁的引擎会拒绝 `--wayfern-identity-file` 里的 overrides，日志是
> `dropping N override(s); this plan does not include custom fingerprints`。

## 建号

```bash
python3 fleet.py create --count 20                 # 自动轮换 57 个机型 + 31 个城市
python3 fleet.py create --count 5 --country US     # 只分美国城市
python3 fleet.py report                            # 唯一性/城市/机型统计
```

每个 profile 落在 `fleet/profiles/<uuid>/`，包含 `metadata.json` 和 Chromium user-data 目录。

## 分配城市 / 代理

```bash
python3 fleet.py assign --profile <id> --city Austin
python3 fleet.py assign --profile <id> --ip 203.0.113.7     # ip-api 反查城市/时区/语言
python3 fleet.py set-proxy --profile <id> --proxy socks5://user:pass@IP:PORT
```

时区、语言、经纬度会写进 profile 的 location；启动器把它们放进 identity 文件。

## 启动

```bash
node launch.mjs --profile fleet/profiles/<id>
node launch.mjs --profile fleet/profiles/<id> --proxy socks5://IP:PORT
```

启动器做的事：

1. 写 `profile/wayfern-identity.json`（identityId / os / 时区 / 语言 / overrides）；
2. 用 `--window-size` 按 persona 屏幕尺寸拉起引擎；
3. 注入字体策略环境变量；
4. 用 `Target.setAutoAttach` 给**每个标签页**（含后续新开）注入 canvas/WebGL/audio 噪声，
   种子由 profile UUID 派生，同一 profile 每次一致、不同 profile 必不相同。

## 验收

```bash
python3 audit_fleet.py 20        # 前 20 台逐台启动、测量、汇总
```

输出 `fleet/audit.jsonl`，每行包含 `hc / 屏幕 / DPR / GPU / canvas / audio / 时区 / 语言 / 字体判定`。
脚本会打印 canvas+audio 的唯一数量与重复对；有重复时退出码为 2。

## 参考数据

50 台实测：canvas 50/50 不同、audio 50/50 不同、机型三元组 50/50 不同、
时区与语言零错配、CJK 字体 50/50 不可见。
