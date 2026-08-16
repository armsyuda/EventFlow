"""EventFlow 디버그 이벤트 로깅.

유저 컴퓨터에서만 재현되는 단위 콤보 드롭다운 문제를 진단하기 위해,
마우스/팝업/편집기 이벤트를 바탕화면 로그 파일로 남긴다.
파일은 append 모드로 쓰므로 앱이 꺼져도 그대로 남아 있다.
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _desktop_dir() -> Path | None:
    """가능한 바탕화면 경로 후보를 순서대로 찾는다."""
    candidates: list[Path | None] = []
    for env in ("USERPROFILE", "HOMEDRIVE"):
        pass
    # 1) OneDrive Desktop (Windows는 Desktop 리다이렉트 시 여기로 감)
    home = Path.home()
    candidates.append(home / "OneDrive" / "Desktop")
    candidates.append(home / "Desktop")
    # 2) 레지스트리 기반 실제 Desktop 경로
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            raw, _ = winreg.QueryValueEx(key, "Desktop")
            expanded = os.path.expandvars(raw)
            candidates.append(Path(expanded))
    except Exception:
        pass
    for cand in candidates:
        if cand is not None and cand.exists():
            return cand
    return None


def _log_path() -> Path:
    desktop = _desktop_dir()
    dest = desktop if desktop is not None else Path.home()
    try:
        return dest / "EventFlow-dropdown-debug.log"
    except Exception:
        return Path.home() / "EventFlow-dropdown-debug.log"


_logger: logging.Logger | None = None
_log_installed = False


def install_dropdown_logger(level: int = logging.DEBUG) -> logging.Logger:
    """바탕화면 로그 파일에 이벤트를 기록하는 로거를 설치하고 반환한다.

    멱등: 이미 설치되어 있으면 기존 로거를 돌려준다.
    """
    global _logger, _log_installed
    if _log_installed and _logger is not None:
        return _logger
    path = _log_path()
    logger = logging.getLogger("eventflow.debug")
    logger.setLevel(level)
    logger.propagate = False
    try:
        handler = RotatingFileHandler(
            str(path), maxBytes=2_000_000, backupCount=1, encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s", "%H:%M:%S"
            )
        )
        logger.addHandler(handler)
    except Exception:
        # 로그 파일을 못 만들면 콘솔로 대체(개발 중 확인용).
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("[dbg] %(message)s"))
        logger.addHandler(handler)
    _logger = logger
    _log_installed = True
    try:
        logger.info("=== EventFlow 디버그 로깅 시작 (버전 %s) ===", _app_version())
    except Exception:
        pass
    return logger


def get_dropdown_logger() -> logging.Logger:
    if _logger is None:
        return install_dropdown_logger()
    return _logger


def _app_version() -> str:
    try:
        from . import __version__
        return __version__
    except Exception:
        return "?"
