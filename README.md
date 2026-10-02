# YASB GUI 中文增强版

基于 [amnweb/yasb-gui](https://github.com/amnweb/yasb-gui) 的 WinUI 3 配置器，增加简体中文、版本适配和完整字段编辑。保留上游 MIT 许可与版权；上游说明见 [README.upstream.md](README.upstream.md)。

## 下载与运行

前往本仓库 [Releases](https://github.com/momoqiqi-qwq/yasb-gui/releases)，下载目标版本的 `YASB-GUI-版本号-x64-portable.zip`，解压后运行 `ygui.exe`。

请保留整个解压目录的 `lib`、`app`、`assets` 和 DLL 文件。Release 中单独提供的 EXE 需要同版本完整包的依赖文件，不能跨版本混用。每个版本分别提供 SHA256 校验文件，旧版本不会被覆盖。

运行环境为 Windows x64，并需要可用的 Windows App SDK Runtime 与 WebView2 Runtime。可执行文件为本地构建的未签名版本。

## 功能

- 简体中文界面、组件名称、设置字段和 Monaco 编辑器命令。
- 目标规则可选择 YASB 2.0.6、2.0.7 与内置开发分支快照。
- 正式版 57 种组件、开发快照 59 种组件的目录、默认配置与完整字段表单。
- 全局、状态栏和组件的高级 YAML 编辑。
- 命令文本、JSON 数据和快捷键三个自定义组件模板。
- 保存前检查官方字段兼容性，保留中文与自定义字段的值。

`style: adaptive` 与 `style_adaptive_exclude` 仅属于开发分支快照，2.0.7 正式版不支持。

## 版本与已知限制

- `v0.0.7`：已有本地中文增强构建的独立归档。
- `v0.1.0`：发布版本，更新版本号、仓库链接、构建与测试工作流。

本次发布尚未实施结构审查提出的优化。CSS 保存的异步状态、空文本保存、切页草稿保留、原子写入、YAML 注释保留和 schema 缓存一致性仍需后续修复。CSS 格式化还可能改变字符串内的连续空格。建议编辑前导出配置备份。

本发行渠道提供便携包；原有应用内 MSIX 安装更新流程不适用于这些 ZIP，请通过 Releases 手动下载新版本到独立目录。

## 源码运行与构建

需要 Python 3.14 和 Windows。

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev,build]"
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check app
.venv/Scripts/python.exe app/scripts/build.py build
.venv/Scripts/python.exe app/scripts/package_release.py 0.1.0
```

源码启动：`run.cmd`。构建输出：`dist/ygui.exe`。发布附件：`release-files/0.1.0/`。打包脚本不会覆盖已存在的版本附件。

构建和测试工作流模板保存在 `docs/workflow-templates/`。当前上传凭据缺少 GitHub 的 workflow 权限，因此模板尚未启用；获得该权限后，可将模板移入 `.github/workflows/`。本次 EXE 和完整包已在 Windows 本地构建和验证，正式 Release 按独立 Git 标签发布，保留旧标签与附件。

详细修改见 [CHANGES-zh_CN.md](CHANGES-zh_CN.md)。

