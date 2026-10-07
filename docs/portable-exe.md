# 单文件便携 EXE

`YASB-GUI-0.4.0-x64-portable.exe` 可以单独复制运行，无需手动解压或安装 Python。与旧的 `YASB-GUI-0.4.0-x64.exe` 不同，它内置完整冻结程序目录：Python 3.14、VC++ DLL、Python 扩展、JSON Schema 数据、中文资源、Monaco、XAML 和社区扩展。

首次启动把资源展开到 `%LOCALAPPDATA%/YASB-GUI/portable/<内容哈希>/`。每次启动校验内置 ZIP 和每个文件的 SHA256，缺失或损坏的缓存文件自动修复；不同包使用独立缓存。无需管理员权限。应用偏好与备份仍使用现有用户数据目录，YASB 配置保持原位置。因此这是免安装的单文件发行包，不是把所有用户数据随 EXE 带走的模式。

## 系统依赖

- Windows x64，需 .NET Framework 4.5 或以上运行启动器；建议 Windows 10/11 自带的 .NET Framework 4.8。
- Windows App Runtime **1.7 x64**，最低 **7000.498.2246.0**。启动器调用官方 Bootstrap API 检查能否真正加载兼容运行库；仅有其他版本不代表兼容。
- Microsoft Edge WebView2 Evergreen Runtime：启动器同时检查运行库注册版本和对应浏览器 EXE 是否存在。
- 实际状态栏仍需用户安装 YASB；GUI 只编辑配置。Proton VPN 扩展也需要用户自己的 VPN 程序。

Windows App Runtime 和 WebView2 是共享系统运行库，未内置于此 EXE。缺失时显示中文提示及微软安装地址，不会静默安装、请求提权或修改系统运行库。启动器的 WebView2 检查不代替完整浏览器创建和编辑交互验证。

微软说明：[Windows App SDK Bootstrap](https://learn.microsoft.com/windows/apps/windows-app-sdk/use-windows-app-sdk-run-time)、[WebView2 分发](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution)。

## 构建与检查

先通过 `app/scripts/build.py build` 生成完整 `dist`，再运行：

```powershell
.venv/Scripts/python.exe app/scripts/build_portable.py
```

脚本检查关键资源、生成全量哈希清单并编译 x64 启动器，拒绝覆盖已有 EXE 或校验文件。构建需要 Windows 自带的 .NET Framework C# 编译器。

```powershell
Start-Process ./YASB-GUI-0.4.0-x64-portable.exe -ArgumentList '--check' -Wait
```

`--check` 展开/校验文件并检查系统运行库，不启动 GUI；在 EXE 同目录写入 `portable-check.txt`，退出码 0 为成功。该目录需要可写。普通双击不会创建此报告。

发布包未签名。本机验证覆盖单独 EXE 在中文路径启动、运行库检查、依赖缓存损坏修复和原生窗口；未在全新 Windows 系统验证。
