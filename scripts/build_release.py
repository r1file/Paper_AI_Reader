from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "Paper AI Reader"
MODULE_NAME = "Paper_AI_Reader"
RELEASE_DIR = ROOT / "release"
EXCLUDE_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "release",
    "venv",
}
EXCLUDE_FILES = {
    ".env",
    "app_config.json",
    "config/settings.xml",
}
EXCLUDE_NAMES = {
    ".DS_Store",
}


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower().replace("amd64", "x86_64")
    return f"{system}-{machine}"


def data_arg(source: str, dest: str) -> str:
    separator = ";" if platform.system() == "Windows" else ":"
    return f"{source}{separator}{dest}"


def clean_build_dirs() -> None:
    for path in (ROOT / "build", ROOT / "dist"):
        if path.exists():
            shutil.rmtree(path)
    RELEASE_DIR.mkdir(exist_ok=True)


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ModuleNotFoundError:
        run([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"])


def build_app(version: str) -> Path:
    clean_build_dirs()
    ensure_pyinstaller()
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--add-data",
        data_arg("config/settings.example.xml", "config"),
        "--add-data",
        data_arg("prompts", "prompts"),
        "gui.py",
    ]
    run(command)

    tag = platform_tag()
    dist_app = ROOT / "dist" / APP_NAME
    if platform.system() == "Darwin":
        dist_app = ROOT / "dist" / f"{APP_NAME}.app"

    if not dist_app.exists():
        raise RuntimeError(f"Expected PyInstaller output was not created: {dist_app}")
    if platform.system() == "Windows" and not (dist_app / f"{APP_NAME}.exe").exists():
        raise RuntimeError(f"Expected Windows executable was not created: {dist_app / f'{APP_NAME}.exe'}")

    archive_path = RELEASE_DIR / f"{MODULE_NAME}-{version}-{tag}.zip"
    if archive_path.exists():
        archive_path.unlink()
    if platform.system() == "Darwin":
        run([
            "ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(dist_app),
            str(archive_path),
        ])
    else:
        archive_base = RELEASE_DIR / f"{MODULE_NAME}-{version}-{tag}"
        archive_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=dist_app.parent, base_dir=dist_app.name))
    return archive_path


def should_exclude(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if relative.name in EXCLUDE_NAMES or relative.suffix == ".spec":
        return True
    if str(relative) in EXCLUDE_FILES:
        return True
    return any(part in EXCLUDE_DIRS for part in relative.parts)


def build_source_zip(version: str) -> Path:
    RELEASE_DIR.mkdir(exist_ok=True)
    target = RELEASE_DIR / f"{MODULE_NAME}-{version}-source.zip"
    if target.exists():
        target.unlink()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in ROOT.rglob("*"):
            if path.is_dir() or should_exclude(path):
                continue
            relative = path.relative_to(ROOT)
            archive.write(path, Path(f"{MODULE_NAME}-{version}") / relative)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Paper AI Reader release artifacts.")
    parser.add_argument("--version", default=os.environ.get("RELEASE_VERSION", "dev"))
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--app-only", action="store_true")
    args = parser.parse_args()

    artifacts: list[Path] = []
    if not args.app_only:
        artifacts.append(build_source_zip(args.version))
    if not args.source_only:
        artifacts.append(build_app(args.version))

    print("Release artifacts:")
    for artifact in artifacts:
        print(f"  {artifact}")


if __name__ == "__main__":
    main()
