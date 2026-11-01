# 编辑可靠性与更新体验优化

本次修改随 v0.4.1 发布。原有 v0.4.0 的 `dist/` 和 `release-files/` 附件未覆盖。

## 修改内容

| 范围 | 结果 | 主要文件 |
|---|---|---|
| CSS 清理 | 保护单双引号、转义字符及 URL；支持撤销；不清除未闭合注释后的文本 | `app/core/editor/code_editor.html`、`app/pages/styles.py` |
| CSS 词法边界 | 能安全移除的注释直接删除；可能合并词法单元的地方保留 `/**/`，避免改变配置含义 | `app/core/editor/code_editor.html` |
| YAML 未保存检测 | 注释、引号及标量样式变化纳入检测；撤回修改后恢复已保存状态 | `app/core/config_manager.py` |
| 组件 YAML | 解析和提取选项保留 round-trip 映射及其注释 | `app/core/widget_helpers.py`、`app/core/code_editor.py` |
| 删除组件 | 清除所有状态栏、所有区域中的重复引用 | `app/core/config_manager.py` |
| 规则缓存 | 按 stable、v2_0_6、development 隔离，验证格式版本、目标版本和来源；使用原子写入 | `app/core/schema_fetcher.py` |
| 下载中的版本切换 | 下载开始时固定目标版本，切换页面设置不会将结果写入另一版本的缓存 | `app/core/schema_fetcher.py` |
| 更新渠道 | 便携版优先获取对应架构的完整 EXE，其次 ZIP；MSIX 按当前进程包身份选择安装附件 | `app/core/updater.py` |
| 更新入口 | 便携版点击下载链接，不执行 Appx 安装或关闭编辑器；版本说明指向当前仓库 | `app/pages/app_settings.py` |
| 启动和反馈 | 恢复使用内置 schema 时的后台更新检查；失败显示错误；未知下载大小显示不定进度 | `app/core/application.py`、`app/pages/app_settings.py` |
| 等待时间 | 移除编辑器初始化、手动更新检查和下载前的固定等待 | 编辑器 HTML、样式/组件/设置页面 |
| 多语言 | 补充便携更新说明和按钮，保持四种语言的键一致 | `app/core/locales/*.json` |

旧的无版本缓存不参与查询；缓存缺失或来源不匹配时，组件层级使用内置快照。表单和保存校验继续使用内置规则，没有改变为联网依赖。

## 验证

在独立测试数据目录中运行，不读取或覆盖实际 YASB 配置。

- `.venv/Scripts/python.exe -m pytest -q -o cache_dir=work/optimization-tests/pytest-cache`：**511 passed, 1 skipped**，无警告。
- `.venv/Scripts/ruff.exe check app tests`：通过。
- `.venv/Scripts/python.exe -m compileall -q app`：通过。
- `node tests/editor_smoke.cjs`：通过，覆盖字符串/URL/转义保护、词法边界、未闭合注释、撤销及取消初始化等待。
- `git diff --check`：通过。
- `.venv/Scripts/python.exe app/scripts/build.py build_exe --build-exe=<项目根>/work/optimization-build`：成功，生成 `work/optimization-build/ygui.exe` 及配套依赖；日志位于 `work/optimization-tests/build.log`。

新增回归用例：`tests/test_reliability_optimizations.py`。原有 schema 用例改为使用按版本保存的缓存路径。

## 原生验证限制

新增 `tests/native_update_smoke.py`，用于在隐藏的真实 WinUI 窗口检查更新按钮、版本说明链接和便携下载点击。当前环境初始化失败：`0x80670016`，无法找到匹配的 Windows App Runtime 1.7 框架。包查询仅显示 CBS 1.6 / 1.8，不能替代程序所需的 1.7 框架。

因此本次未确认真实 WinUI/WebView 的完整端到端交互。安装满足现有依赖要求的运行库后，可运行：

```powershell
.venv/Scripts/python.exe tests/native_update_smoke.py
```

测试脚本隔离设置与缓存，并拦截浏览器打开操作；不访问远端或实际安装更新。独立构建仍需要项目既有的 Windows App Runtime 1.7 和 WebView2 运行环境。

草稿跨重启恢复、已有组件批量操作和多文件联合事务不属于本次修改。
