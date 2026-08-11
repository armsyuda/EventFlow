from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import __version__

REPOSITORY = "armsyuda/EventFlow"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
PREFERRED_ASSET = "EventFlow-Windows.zip"


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    tag: str
    asset_url: str
    asset_name: str
    asset_digest: str | None
    release_url: str
    notes: str


class UpdateCheckError(RuntimeError):
    pass


def version_tuple(value: str) -> tuple[int, ...]:
    clean = value.strip().lstrip("vV").split("-", 1)[0]
    try:
        return tuple(int(part) for part in clean.split("."))
    except ValueError:
        return (0,)


def check_for_update(timeout: float = 6.0) -> UpdateInfo | None:
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"EventFlow/{__version__}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            release = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise UpdateCheckError("GitHub Release를 확인할 수 없습니다.") from exc
    tag = str(release.get("tag_name") or "")
    if not tag or version_tuple(tag) <= version_tuple(__version__):
        return None
    assets = list(release.get("assets") or [])
    asset = next((entry for entry in assets if entry.get("name") == PREFERRED_ASSET), None)
    if asset is None:
        asset = next((entry for entry in assets if str(entry.get("name", "")).lower().endswith(".zip")
                      and "eventflow" in str(entry.get("name", "")).lower()), None)
    if asset is None:
        return UpdateInfo(tag.lstrip("vV"), tag, "", "", None,
                          str(release.get("html_url") or RELEASES_URL), str(release.get("body") or ""))
    url = str(asset.get("browser_download_url") or "")
    expected_prefix = f"https://github.com/{REPOSITORY}/releases/download/"
    if not url.startswith(expected_prefix):
        return None
    return UpdateInfo(
        tag.lstrip("vV"), tag, url, str(asset.get("name") or PREFERRED_ASSET),
        str(asset.get("digest")) if asset.get("digest") else None,
        str(release.get("html_url") or RELEASES_URL), str(release.get("body") or ""),
    )


def download_update(info: UpdateInfo, timeout: float = 90.0) -> Path:
    if not info.asset_url:
        raise ValueError("자동 설치용 Windows ZIP 파일이 릴리스에 없습니다.")
    update_dir = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "EventCheckList" / "updates"
    update_dir.mkdir(parents=True, exist_ok=True)
    destination = update_dir / f"EventFlow-{info.version}.zip"
    request = urllib.request.Request(info.asset_url, headers={"User-Agent": f"EventFlow/{__version__}"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=timeout) as response, destination.open("wb") as handle:
        while chunk := response.read(1024 * 1024):
            handle.write(chunk); digest.update(chunk)
    if info.asset_digest and info.asset_digest.lower().startswith("sha256:"):
        expected = info.asset_digest.split(":", 1)[1].lower()
        if digest.hexdigest().lower() != expected:
            destination.unlink(missing_ok=True)
            raise ValueError("업데이트 파일의 SHA-256 검증에 실패했습니다.")
    return destination


def is_packaged_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def launch_installer(archive: Path, info: UpdateInfo, process_id: int) -> None:
    if not is_packaged_app():
        raise RuntimeError("자동 설치는 패키징된 EventFlow.exe에서만 실행할 수 있습니다.")
    executable = Path(sys.executable).resolve()
    install_dir = executable.parent
    if executable.name.lower() != "eventflow.exe" or install_dir.parent == install_dir:
        raise RuntimeError("이플 설치 폴더를 안전하게 확인할 수 없습니다.")
    script_dir = archive.parent
    script_path = script_dir / f"apply-{info.version}.ps1"

    def ps(value: Path | str) -> str:
        return str(value).replace("'", "''")

    staging = script_dir / f"staging-{info.version}"
    old_dir = install_dir.with_name(f"{install_dir.name}.update-old")
    script = f"""$ErrorActionPreference = 'Stop'
$archive = '{ps(archive)}'
$staging = '{ps(staging)}'
$install = '{ps(install_dir)}'
$old = '{ps(old_dir)}'
$exe = Join-Path $install 'EventFlow.exe'
for ($i = 0; $i -lt 120; $i++) {{
    if (-not (Get-Process -Id {int(process_id)} -ErrorAction SilentlyContinue)) {{ break }}
    Start-Sleep -Milliseconds 500
}}
if (Test-Path -LiteralPath $staging) {{ Remove-Item -LiteralPath $staging -Recurse -Force }}
New-Item -ItemType Directory -Path $staging | Out-Null
Expand-Archive -LiteralPath $archive -DestinationPath $staging -Force
$payload = $staging
$nested = Join-Path $staging 'EventFlow'
if (Test-Path -LiteralPath (Join-Path $nested 'EventFlow.exe')) {{ $payload = $nested }}
if (-not (Test-Path -LiteralPath (Join-Path $payload 'EventFlow.exe'))) {{ throw '업데이트 파일에 EventFlow.exe가 없습니다.' }}
if (Test-Path -LiteralPath $old) {{ Remove-Item -LiteralPath $old -Recurse -Force }}
try {{
    Move-Item -LiteralPath $install -Destination $old
    Move-Item -LiteralPath $payload -Destination $install
    Start-Process -FilePath $exe -WindowStyle Normal
}} catch {{
    if (Test-Path -LiteralPath $install) {{ Remove-Item -LiteralPath $install -Recurse -Force }}
    if (Test-Path -LiteralPath $old) {{ Move-Item -LiteralPath $old -Destination $install }}
    throw
}}
"""
    script_path.write_text(script, encoding="utf-8-sig")
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(script_path)],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )
