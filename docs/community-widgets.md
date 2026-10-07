# 社区扩展（v0.3.0）

入口：**组件 → 添加组件 → 社区扩展**。提供设备状态、截图（全部屏幕 / 选择区域）、Proton VPN 四个模板。确认后添加到选中的状态栏位置；仍需点击保存才能写入实际 YASB 配置。添加后可通过原有表单或高级 YAML 修改完整选项。

## USB / 串口设备状态

使用 [MochaGlass](https://github.com/Hyacinthe-primus/Project_MochaGlass) 的 `device_status.exe`，固定上游 v1.0.2，Windows x64，MIT 许可。

- 留空程序路径时使用内置版本；也可选择输出 `compact`、`count`、`tooltip` 三个字段的 JSON 程序。
- 刷新间隔为 5–3600 秒，默认 5 秒。设备识别依赖 Windows 驱动与系统枚举，上游缓存也可能导致刷新延迟。
- 默认标签显示设备摘要，点击切换数量，悬停显示详细信息。
- 内置文件在安装前校验 SHA256：`0e85bd331a3f847eef7280282a6267de58a107b96bb50b4387302d6a3d74652d`。
- 发布来源、许可证和对应主要源码保留于 `app/extensions/vendor/`。完整源码及依赖清单见上游 v1.0.2 标签。

## 截图

功能参考 [Personnal-YASB-Scripts](https://github.com/Lerakei-0/Personnal-YASB-Scripts)，本项目独立实现 PowerShell 脚本，未复制该仓库代码。

- **全部屏幕**：捕获当前交互式桌面的全部显示器，保存到可设置的绝对路径，默认 `Pictures/YASB_Screenshots`。尝试将图片复制到剪贴板；剪贴板繁忙不影响已保存的 PNG。使用唯一文件名，避免覆盖旧截图。
- **选择区域**：打开 Windows `ms-screenclip:` 协议；由 Windows 截图工具控制选择、剪贴板与保存。不会承诺自动保存到全屏截图目录。
- 无需 Python/Pillow。需要 Windows PowerShell、.NET、可用的交互式桌面；区域截图还需要 Windows 截图工具。

## Proton VPN 快捷入口

功能参考同一社区项目，本项目独立实现内置脚本。

- 自动检测常见 `Program Files/Proton/VPN/v*/ProtonVPN.Client.exe` 路径，可通过“选择程序”修改。
- 默认点击打开客户端。可勾选“切换已有托盘弹窗”，匹配已有 `Proton VPN (tray)` 窗口；未找到时打开客户端。
- 不强制移动弹窗位置，也不执行 VPN 连接、断开或网络设置修改。不同客户端版本的窗口标识可能不同。

## 文件安装与升级

配套文件仅在确认添加时复制到应用数据目录的 `YASB-GUI/extensions/<SHA256>/`，配置引用该稳定位置。移动配置器安装目录不影响已有组件；不同脚本版本保留各自目录，不覆盖旧配置引用的版本。校验失败时提示错误，不覆盖用户改过的副本。

Windows PowerShell 命令使用 `-ExecutionPolicy Bypass` 运行所选本地脚本，仅影响该进程，不修改系统策略。命令关闭 shell 执行，路径中的空格、中文和 `&` 按字面处理；设备轮询命令另使用编码参数兼容 YASB 的空格拆分规则。

这些组件由 **YASB 本体**执行，配置器不后台轮询或自动启动 Proton VPN，也不在添加时截屏。设备 JSON 与带空格路径的轮询已实测；截图桌面/剪贴板及真实 Proton VPN 弹窗仍需在目标设备上验证。
