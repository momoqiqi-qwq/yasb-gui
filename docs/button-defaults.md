# GUI 添加按钮的统一默认设置

通过应用列表编辑器、命令预设、社区组件、表单和 YAML 入口确认配置时，按钮统一经过 `prepare_button_options`：

- APP 列表中的新条目使用 PNG；每个 APP 有独立圆角边框。
- 执行命令的 CustomWidget 保留已有 class，并增加 `yasbgui-button`；组件容器使用 12px 圆角、细边框和透明背景。
- 新增 HomeWidget 和 PowerMenuWidget 的图标使用 PNG；容器使用同样的边框。普通文字和 `{data}` 等动态标签保留为文字。
- 默认显示尺寸 20px，图标标签至少留出 24px 高度。PNG 根据实际轮廓居中生成，边缘保留透明区域，避免字体基线和字形超出布局引起截断。

12 个命令预设的 PNG 随程序打包。确认配置时，图标复制到当前配置目录的 `icons/yasb-gui/`，保存的路径不依赖便携程序的解压缓存。自定义字符优先使用安装的 Nerd Font，其他字体作为回退；找不到字符或图片时显示错误，不静默替换。用户自行选择的图片、已有 APP 图标、启动命令和显式设置的图标尺寸保留。

CSS 默认块先放入样式草稿，跟随主窗口“保存”写入。首次打开样式页面不会丢弃此草稿；已打开的 Monaco 使用保留撤销的修改入口。默认块放在已有 CSS 前面，之后的同等优先级自定义规则可覆盖它。再次添加不会重复插入或覆盖修改过的默认块。取消配置对话框不会写入配置或 CSS；确认后生成的图标文件属于可复用资源缓存。

验证命令：

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe work/default_button_native.py
.venv/Scripts/python.exe work/button_preset_smoke.py
```

全量测试结果为 490 passed、1 skipped，覆盖配置隔离、图标持久路径、全部命令预设、CSS 草稿和自定义保留。原生渲染使用已安装 YASB 2.0.6 的真实 CustomWidget、ApplicationsWidget、HomeWidget 和 PowerMenuWidget，在 100%、125%、150%、200% 缩放下检查 16 个图标标签和 PNG 的透明边缘；原生 WinUI 验证使用 ButtonAutomationPeer 调用编辑按钮，不启动用户应用。

本次更新了构建与便携版本的资源检查，但未重新打包 EXE。
