# apps 应用列表编辑器

点击 `yasb.applications.ApplicationsWidget` 类型的卡片，进入专用应用列表编辑器；右键的“编辑”和“表单编辑”也可进入。停用组件同样支持。右键“编辑 YAML…”保留原来的完整配置编辑入口。

1. 点击“浏览并添加应用…”，在 Windows 文件选择窗口中选择 `.exe`、`.lnk` 或 `.url`。使用 Ctrl / Shift 多选，同批次中重复的启动命令不会重复添加。
2. 编辑应用名称、图标字符或图片路径、启动命令；也可选择图标图片、上移、下移、删除。
   可从预设下拉框选择常用命令，再点击“使用此预设”添加；也可“添加自定义命令按钮”，输入任意启动命令。
3. 点击“应用修改”写入编辑器内存中的配置，再使用主窗口的保存操作保存配置文件。取消不会修改原列表。新增 apps 组件也使用此界面，确认前不会创建组件。

新条目使用通用图标，不自动提取 EXE 内的图标。其他组件选项及原有启动命令不会被重写。快捷方式保留为快捷方式路径，交由 Windows 启动，以保留其参数和工作目录。

新增条目使用 `powershell.exe -NoProfile -EncodedCommand` 调用 `Start-Process -FilePath`。这样路径中的空格、中文、单引号和 shell 特殊字符可以穿过 YASB 的空白分词启动逻辑。选择文件时不会执行文件。

首次实现的验证（新增预设后的验证见 [button-audit.md](button-audit.md)）：

- `.venv/Scripts/python.exe -m pytest -q`：439 passed，1 skipped。
- `.venv/Scripts/ruff.exe check app/core/apps_editor.py app/ui/apps_editor.py tests/test_apps_editor.py app/pages/widgets.py`：通过。
- `.venv/Scripts/python.exe work/apps_editor_smoke.py`：原生 WinUI 控件构造、直接读取文本草稿、取消隔离、应用修改、空图标校验通过。该验证使用测试 dialog 包装，未自动操作 Explorer 文件选择窗口。
- `git diff --check`：通过。

未执行用户配置中的应用、未验证真实 YASB 点击启动，也未重新打包现有 EXE；本次修改作用于源码运行版本。
