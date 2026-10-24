# 许可与第三方说明

## 本项目

- 许可：**GNU Affero General Public License v3.0**（见 `LICENSE`）。
- 本仓库是对 [zhom/donutbrowser](https://github.com/zhom/donutbrowser) 的修改版本，
  以补丁形式提供完整改动（`patches/donut-local.patch`），符合 AGPL-3.0 对衍生作品的要求。
- 上游版权归 Donut Browser 作者所有。

## 未包含的内容

- **不包含** Donut Browser 官方安装包或任何厂商二进制。
- **不包含** Wayfern 引擎（`Wayfern.app`，约 2.4 GB）。它由 App 首次运行时从官方渠道下载，
  使用须遵守其自身条款。
- **不包含** 任何用户数据、profile、代理凭据或证书。

## 使用范围

- 仅供本机自用、研究与学习。
- 云端服务（备份、团队、远程会话、云调度）仍由服务端鉴权，本项目不提供绕过。
- 使用第三方服务时请遵守其条款；由此产生的后果由使用者自行承担。

## 字体与指纹工具

- `extras/font-policy/font_policy.c` 与本仓库其他脚本均为本项目原创，同样以 AGPL-3.0 发布。
- 字体裁剪只影响本机引擎副本，不修改系统字体。
