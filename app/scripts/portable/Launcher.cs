using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class Launcher
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool SetDllDirectory(string path);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr AddDllDirectory(string path);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetDefaultDllDirectories(uint flags);
    [DllImport("Microsoft.WindowsAppRuntime.Bootstrap.dll", CharSet = CharSet.Unicode)]
    static extern int MddBootstrapInitialize2(uint version, string tag, ulong minimum, uint options);
    [DllImport("Microsoft.WindowsAppRuntime.Bootstrap.dll")]
    static extern void MddBootstrapShutdown();

    static string Hash(Stream stream)
    {
        using (var sha = SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }

    static void NoLinks(string path)
    {
        for (var current = new DirectoryInfo(path); current != null; current = current.Parent)
            if (current.Exists && (current.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new IOException("便携缓存路径包含链接，请使用普通本地目录。");
    }

    static bool HasWebView()
    {
        const string key = @"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}";
        foreach (var hive in new[] { RegistryHive.LocalMachine, RegistryHive.CurrentUser })
            foreach (var view in new[] { RegistryView.Registry32, RegistryView.Registry64 })
                using (var root = RegistryKey.OpenBaseKey(hive, view))
                using (var client = root.OpenSubKey(key))
                {
                    Version version;
                    if (client != null && Version.TryParse(Convert.ToString(client.GetValue("pv")), out version)
                        && version.Major > 0)
                    {
                        foreach (var folder in new[] {
                            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
                            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData) })
                            if (File.Exists(Path.Combine(folder, "Microsoft", "EdgeWebView", "Application", version.ToString(), "msedgewebview2.exe")))
                                return true;
                    }
                }
        return false;
    }

    [STAThread]
    static int Main(string[] args)
    {
        bool check = args.Length == 1 && args[0] == "--check";
        string report = Path.Combine(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location), "portable-check.txt");
        try
        {
            if (!Environment.Is64BitOperatingSystem || !Environment.Is64BitProcess)
                throw new PlatformNotSupportedException("需要 Windows x64。");
            var assembly = Assembly.GetExecutingAssembly();
            string[] manifest;
            using (var reader = new StreamReader(assembly.GetManifestResourceStream("manifest"), Encoding.UTF8))
                manifest = reader.ReadToEnd().Split(new[] { '\n' }, StringSplitOptions.RemoveEmptyEntries);
            string identity = manifest[0].Trim();
            string cache = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "YASB-GUI", "portable", identity);
            NoLinks(cache);
            Directory.CreateDirectory(cache);
            using (var mutex = new Mutex(false, "Local\\YASB-GUI-portable-" + identity))
            {
                bool acquired;
                try { acquired = mutex.WaitOne(TimeSpan.FromMinutes(2)); }
                catch (AbandonedMutexException) { acquired = true; }
                if (!acquired) throw new IOException("另一进程正在展开便携依赖，请稍后重试。");
                try
                {
                    using (var payload = assembly.GetManifestResourceStream("payload"))
                    {
                        if (Hash(payload) != identity) throw new IOException("内置依赖包校验失败，请重新下载 EXE。");
                        payload.Position = 0;
                        using (var archive = new ZipArchive(payload, ZipArchiveMode.Read))
                            for (int i = 2; i < manifest.Length; i++)
                            {
                                var parts = manifest[i].TrimEnd('\r').Split('\t');
                                string path = Path.GetFullPath(Path.Combine(cache, parts[1]));
                                if (!path.StartsWith(cache + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                                    throw new IOException("依赖文件路径非法。");
                                NoLinks(Path.GetDirectoryName(path));
                                if (File.Exists(path) && (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
                                    throw new IOException("依赖文件不能是链接。");
                                bool valid = false;
                                if (File.Exists(path)) using (var file = File.OpenRead(path)) valid = Hash(file) == parts[0];
                                if (valid) continue;
                                Directory.CreateDirectory(Path.GetDirectoryName(path));
                                var entry = archive.GetEntry(parts[1]);
                                if (entry == null) throw new IOException("依赖文件缺失：" + parts[1]);
                                string temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
                                try
                                {
                                    using (var source = entry.Open()) using (var output = File.Create(temporary)) source.CopyTo(output);
                                    using (var file = File.OpenRead(temporary))
                                        if (Hash(file) != parts[0]) throw new IOException("依赖校验失败：" + parts[1]);
                                    if (File.Exists(path)) File.Replace(temporary, path, null);
                                    else File.Move(temporary, path);
                                }
                                finally { if (File.Exists(temporary)) File.Delete(temporary); }
                            }
                    }
                }
                finally { mutex.ReleaseMutex(); }
            }
            var runtime = manifest[1].Trim().Split('\t');
            var release = runtime[0].Split('.');
            var minimum = runtime[1].Split('.');
            uint versionNumber = (uint.Parse(release[0]) << 16) | uint.Parse(release[1]);
            ulong minimumNumber = (ulong.Parse(minimum[0]) << 48) | (ulong.Parse(minimum[1]) << 32)
                | (ulong.Parse(minimum[2]) << 16) | ulong.Parse(minimum[3]);
            if (!SetDefaultDllDirectories(0x1000) || AddDllDirectory(cache) == IntPtr.Zero
                || AddDllDirectory(Path.Combine(cache, "lib")) == IntPtr.Zero)
                throw new IOException("无法配置便携 DLL 搜索路径。");
            SetDllDirectory(Path.Combine(cache, "lib"));
            int result = MddBootstrapInitialize2(versionNumber, null, minimumNumber, 0);
            if (result < 0)
                throw new InvalidOperationException("缺少兼容的 Windows App Runtime " + runtime[0] + " x64（至少 " + runtime[1]
                    + "）。\n请安装微软运行库后重试：\nhttps://learn.microsoft.com/windows/apps/windows-app-sdk/downloads\n错误码：0x" + result.ToString("X8"));
            MddBootstrapShutdown();
            if (!HasWebView())
                throw new InvalidOperationException("缺少 Microsoft Edge WebView2 Runtime。\n请安装 Evergreen x64 运行库后重试：\nhttps://developer.microsoft.com/microsoft-edge/webview2/");
            SetDllDirectory(null);
            if (check)
            {
                File.WriteAllText(report, "PASS\r\nCache: " + cache + "\r\nFiles: " + (manifest.Length - 2)
                    + "\r\nWindows App Runtime: compatible\r\nWebView2: registered and executable present\r\n", Encoding.UTF8);
                return 0;
            }
            using (var process = Process.Start(new ProcessStartInfo(Path.Combine(cache, "ygui.exe"))
                { WorkingDirectory = cache, UseShellExecute = false }))
            { process.WaitForExit(); return process.ExitCode; }
        }
        catch (Exception exception)
        {
            if (check) File.WriteAllText(report, "FAIL\r\n" + exception.Message, Encoding.UTF8);
            else MessageBox.Show(exception.Message, "YASB-GUI 便携版：依赖检查", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
