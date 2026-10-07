"""Create a single-file Windows launcher with a verified frozen payload."""

import hashlib
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build():
    import sys

    sys.path.insert(0, str(ROOT / "app"))
    from core.constants import APP_VERSION
    from winui3.microsoft.windows.applicationmodel.dynamicdependency import bootstrap

    dist = ROOT / "dist"
    required = [
        "ygui.exe",
        "python314.dll",
        "vcruntime140.dll",
        "msvcp140.dll",
        "lib/library.zip",
        "lib/Microsoft.WindowsAppRuntime.Bootstrap.dll",
        "lib/jsonschema_specifications/schemas",
        "lib/core/schemas",
        "lib/core/locales",
        "lib/core/editor",
        "lib/core/button_icons",
        "app/xaml",
        "app/extensions",
    ]
    for name in required:
        if not (dist / name).exists():
            raise SystemExit(f"Required dependency missing: {name}. Rebuild dist first.")
    destination = ROOT / "release-files" / APP_VERSION
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / f"YASB-GUI-{APP_VERSION}-x64-portable.exe"
    checksum = output.with_suffix(".sha256")
    if output.exists() or checksum.exists():
        raise SystemExit("Refusing to overwrite existing portable artifacts")
    compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    if not compiler.is_file():
        raise SystemExit(".NET Framework C# compiler is missing")
    with tempfile.TemporaryDirectory(prefix="yasb-portable-") as temporary:
        temporary = Path(temporary)
        payload = temporary / "payload.zip"
        files = sorted(path for path in dist.rglob("*") if path.is_file())
        lines = []
        with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in files:
                relative = path.relative_to(dist).as_posix()
                archive.write(path, relative)
                lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}\t{relative}")
        manifest = temporary / "manifest.txt"
        manifest.write_text(
            hashlib.sha256(payload.read_bytes()).hexdigest()
            + "\n"
            + f"{bootstrap.bootstrap.RELEASE_VERSION}\t{bootstrap.bootstrap.RUNTIME_VERSION}\n"
            + "\n".join(lines)
            + "\n",
            encoding="utf-8",
        )
        staged = temporary / output.name
        subprocess.run(
            [
                str(compiler),
                "/nologo",
                "/target:winexe",
                "/platform:x64",
                "/optimize+",
                "/reference:System.Windows.Forms.dll",
                "/reference:System.IO.Compression.dll",
                f"/win32icon:{ROOT / 'assets/app.ico'}",
                f"/resource:{payload},payload",
                f"/resource:{manifest},manifest",
                f"/out:{staged}",
                str(ROOT / "app/scripts/portable/Launcher.cs"),
            ],
            check=True,
        )
        output.write_bytes(staged.read_bytes())
    checksum.write_text(f"{hashlib.sha256(output.read_bytes()).hexdigest()}  {output.name}\n", encoding="ascii")
    print(f"Created {output} ({output.stat().st_size:,} bytes); {len(files)} verified dependencies")


if __name__ == "__main__":
    build()
