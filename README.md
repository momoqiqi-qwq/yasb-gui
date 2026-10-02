# YASB GUI 中文增强版

**用中文编辑 YASB 状态栏、组件与样式，保留直接编写配置的自由。**

[项目介绍](https://momoqiqi-qwq.github.io/yasb-gui/) · [下载 v0.2.0 完整便携包](https://github.com/momoqiqi-qwq/yasb-gui/releases/download/v0.2.0/YASB-GUI-0.2.0-x64-portable.zip) · [版本记录](https://github.com/momoqiqi-qwq/yasb-gui/releases) · [反馈问题](https://github.com/momoqiqi-qwq/yasb-gui/issues)

这是基于 [amnweb/yasb-gui](https://github.com/amnweb/yasb-gui) 的 Windows 图形配置器，使用 **WinUI 3 + Python**。它负责编辑配置，状态栏和组件由 [YASB 本体](https://github.com/amnweb/yasb)运行。保留上游 MIT 许可与版权；原版说明见 [README.upstream.md](README.upstream.md)。

## 可以做什么

- **用中文调整配置**：界面、组件名称、设置字段和 Monaco 编辑器命令提供简体中文支持。
- **按版本编辑**：内置 YASB 2.0.6、2.0.7 和开发分支快照规则；正式版 57 种组件，开发快照 59 种组件。
- **表单与代码编辑**：全局、状态栏和组件支持完整字段表单及高级 YAML；样式使用 CSS 编辑器。
- **从模板开始自定义**：命令文本、JSON 数据和快捷键三个 CustomWidget 模板；需要配套脚本或数据来源。
- **按习惯设置编辑器**：换行、缩略图、行号、CSS 缩进、空白字符、括号颜色，以及字体、字号和主题。
- **让保存更稳妥**：保存前默认备份旧文件，支持数量限制；配置、样式和偏好采用原子写入。
- **保留当前编辑进度**：CSS 切页保留本次运行中的草稿与撤销历史，支持 Ctrl+S 和从磁盘重新载入。

独立布局或复杂弹窗需要在 YASB 本体中编写 Python 组件，配置器不会自动生成组件实现。

## 下载与运行

1. 在 Windows x64 上准备好 YASB 及其配置，并安装可用的 Windows App SDK Runtime 与 WebView2 Runtime。
2. 下载 [v0.2.0 完整 ZIP](https://github.com/momoqiqi-qwq/yasb-gui/releases/download/v0.2.0/YASB-GUI-0.2.0-x64-portable.zip)，解压到独立目录。
3. 运行 `ygui.exe`，选择与你使用的 YASB 版本相匹配的配置规则。

**请保留整个解压目录的 `lib`、`app`、`assets` 和 DLL 文件。** 单独的 EXE 需要同版本完整包的依赖，不能跨版本混用。每个版本提供 [SHA256 校验文件](https://github.com/momoqiqi-qwq/yasb-gui/releases/download/v0.2.0/YASB-GUI-0.2.0-SHA256SUMS.txt)。

便携版为本地构建的未签名版本。更新时从 Releases 下载新版本到独立目录；原有应用内 MSIX 安装更新流程不适用于 ZIP。

## v0.2.0 更新

新增 **9 项设置**：启动页面、保存前自动备份、备份保留数量，以及 6 项编辑器选项。

修复 CSS 保存状态提前清除、空文本无法保存、切页草稿丢失、右键菜单无法访问编辑器，以及清缓存删除应用偏好等问题。默认按配置目录和文件分别保留最近 10 份备份，可选择 5/10/20/50 份或关闭自动备份。

本地验证：383 项测试通过、1 项跳过；Python 静态检查、编辑器桥接测试、构建和原生设置页面启动通过。完整记录见 [体验优化清单](docs/experience-review.md) 和 [中文变更说明](CHANGES-zh_CN.md)。

## 兼容性与当前限制

- `style: adaptive` 和 `style_adaptive_exclude` 属于内置开发快照，不属于 YASB 2.0.7 正式版。
- 开发快照随本仓库版本提供，不代表始终同步远端 main。
- 草稿暂不跨重启恢复；外部文件修改冲突检测、多文件联合保存和 schema 缓存同步仍待完善。
- CSS 清理注释仍采用简单规则，应谨慎使用。
- 编辑器桥接测试使用 Monaco 替身，完整 WebView 交互尚未端到端验证。

## 源码运行与构建

需要 Python 3.14 和 Windows。

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev,build]"
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check app tests/conftest.py tests/test_editing_experience.py
node tests/editor_smoke.cjs
.venv/Scripts/python.exe app/scripts/build.py build
.venv/Scripts/python.exe app/scripts/package_release.py 0.2.0
```

源码启动：`run.cmd`。构建输出：`dist/ygui.exe`。版本附件：`release-files/0.2.0/`。打包脚本拒绝覆盖已有附件；旧版本和标签继续保留。

CI 工作流模板位于 `docs/workflow-templates/`，启用时移入 `.github/workflows/`。介绍页由根目录 `index.html` 和 `website/` 静态资源组成，可通过 GitHub Pages 从 `main` 的根目录发布。

## 上游与许可

本项目是社区中文增强版，与上游项目保持独立发行。感谢 [amnweb/yasb-gui](https://github.com/amnweb/yasb-gui) 和 [amnweb/yasb](https://github.com/amnweb/yasb)。遵循 [MIT License](LICENSE)，保留原作者版权声明。
