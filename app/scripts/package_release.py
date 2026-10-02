import argparse
import hashlib
import shutil
import zipfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("version")
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
dist = root / "dist"
destination = root / "release-files" / args.version
destination.mkdir(parents=True, exist_ok=True)
prefix = f"YASB-GUI-{args.version}-x64"
exe = destination / f"{prefix}.exe"
archive = destination / f"{prefix}-portable.zip"
if exe.exists() or archive.exists():
    raise SystemExit("Refusing to overwrite an existing version package")
shutil.copy2(dist / "ygui.exe", exe)
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as output:
    for path in sorted(dist.rglob("*")):
        if path.is_file():
            output.write(path, path.relative_to(dist).as_posix())
    output.writestr(
        "使用说明.txt",
        "解压完整 ZIP 后运行 ygui.exe。请保留 lib、app、assets 和 DLL 文件。单独下载的 EXE 需要同版本 ZIP 中的依赖文件。\n",
    )
checksums = []
for path in (exe, archive):
    with path.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    checksums.append(f"{checksum}  {path.name}")
(destination / f"YASB-GUI-{args.version}-SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
print(destination)
for path in destination.iterdir():
    print(f"{path.name}: {path.stat().st_size} bytes")
