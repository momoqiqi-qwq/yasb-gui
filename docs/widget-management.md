# 组件搜索与批量管理

本次更新随 v0.4.1 发布。已有 v0.4.0 的 `dist/` 和 `release-files/` 附件未覆盖。

## 使用方法

1. 打开“组件”，选择要管理的状态栏。再次进入页面会保留当前栏及搜索文本；该栏已删除时回退到第一个栏。
2. 在搜索框输入组件实例名称、本地化类型名称、类型路径或分类。搜索忽略大小写，以空格分隔的关键词需要同时匹配，例如 `clock 时钟`。清空输入恢复完整列表。
3. 勾选组件或使用“全选筛选结果”。同名组件在不同区域重复出现时同步勾选，操作按组件名称计数。更改筛选条件、切换状态栏或重新进入页面会清空选择。
4. 使用批量工具栏执行操作，主窗口“保存”才会写入配置文件。

| 操作 | 行为 |
|---|---|
| 复制所选 | 创建独立配置，自动分配 `_1`、`_2` 等可用名称；在当前栏各原引用之后插入副本。未在当前栏使用的组件，其副本也保持未启用。 |
| 添加或移动到 | 从当前栏各区域移除所选组件的旧引用，再按页面顺序向目标区域末尾各添加一次；可同时处理已启用与未启用组件。 |
| 在当前栏停用 | 删除当前栏各区域中所选组件的全部引用，保留组件定义。已停用的组件无需更改。 |

批量移动和停用不会修改其他状态栏。这里的“未启用”仅表示未在当前栏使用，组件可能正在其他栏使用。

右键菜单的单项移动、复制和停用仍只处理点击区域中的一个引用；它们不会同时改动其他区域里的同名组件。

未启用组件的右键菜单也提供“复制”。没有任何状态栏时，仍可查看、编辑和复制现有组件；添加与移动入口在创建状态栏后可用。批量工具栏使用原生 CommandBar，窗口空间不足时可从溢出菜单访问操作。

## 实现与可靠性

- 搜索只调整已有行的可见性，不重复创建 XAML、菜单或事件处理器；筛选后的上下移动仍按真实配置顺序执行。
- 元数据使用类型路径字典查询，移除每行遍历整个注册表的代码及读取后未使用的旧注册表文件。
- 单项启用、移动、复制与批量操作共用校验核心。无效选择、目标或区域结构会在修改前拒绝，避免假成功和部分修改。
- 副本深拷贝嵌套配置，保留 YAML 注释、引号和副本内的别名关系；重新分配锚点，避免副本与原组件共享修改。
- 复制当前栏和区域引用后再提交，避免 YAML 别名将变更传播到其他栏或区域。
- 保留既有保存前校验、备份及外部冲突保护；不增加自动保存行为。

## 验证

回归用例位于 `tests/test_widget_management.py`、`tests/test_widget_management_page.py`。原生交互脚本 `tests/native_widgets_smoke.py` 使用独立测试配置和偏好，不读取或覆盖用户的 YASB 配置。

```powershell
.venv/Scripts/python.exe -m pytest -q -o cache_dir=work/feature-tests/pytest-cache
.venv/Scripts/ruff.exe check app tests
.venv/Scripts/python.exe -m compileall -q app
node tests/editor_smoke.cjs
.venv/Scripts/python.exe tests/native_widgets_smoke.py
```

本轮结果：**564 passed, 1 skipped**；Ruff、Python 编译检查、编辑器桥接测试及 `git diff --check` 通过。原生 WinUI 脚本通过真实控件事件验证搜索、复选框同步、批量操作、状态栏记忆、无状态栏菜单禁用，以及明暗主题和窄页面命令溢出。

独立构建命令：

```powershell
.venv/Scripts/python.exe app/scripts/build.py build_exe --build-exe=E:/E-Develop-Project/yasb-gui/work/widget-management-build
```

构建成功，输出 `work/widget-management-build/ygui.exe` 及配套依赖；运行时需要保留整个目录。构建日志为 `work/feature-tests/build.log`。已用 `work/widget-management-launch/` 内的示例配置和独立偏好启动生成的 EXE，确认主窗口标题为 `YASB GUI`、窗口句柄非零且进程响应正常。

以上验证均未覆盖实际 YASB 配置，已有发行文件未改动。
