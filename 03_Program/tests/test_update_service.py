from __future__ import annotations

import hashlib
import io
import json
import urllib.error
import pytest

from event_checklist import update_service


class Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *_args): self.close()


def test_new_release_is_detected(monkeypatch):
    payload = {
        "tag_name": "v0.3.4",
        "html_url": "https://github.com/armsyuda/EventFlow/releases/tag/v0.3.4",
        "body": "새 기능",
        "assets": [{
            "name": "EventFlow-Windows.zip",
            "browser_download_url": "https://github.com/armsyuda/EventFlow/releases/download/v0.3.4/EventFlow-Windows.zip",
            "digest": "sha256:abc",
        }],
    }
    monkeypatch.setattr(update_service.urllib.request, "urlopen", lambda *_args, **_kwargs: Response(json.dumps(payload).encode()))
    info = update_service.check_for_update()
    assert info and info.version == "0.3.4"
    assert info.asset_name == "EventFlow-Windows.zip"


def test_same_release_does_not_enable_update(monkeypatch):
    payload = {"tag_name": "v0.3.3", "assets": []}
    monkeypatch.setattr(update_service.urllib.request, "urlopen", lambda *_args, **_kwargs: Response(json.dumps(payload).encode()))
    assert update_service.check_for_update() is None


def test_download_verifies_github_digest(monkeypatch, tmp_path):
    content = b"event-flow-update"
    digest = hashlib.sha256(content).hexdigest()
    info = update_service.UpdateInfo(
        "0.3.2", "v0.3.2",
        "https://github.com/armsyuda/EventFlow/releases/download/v0.3.2/EventFlow-Windows.zip",
        "EventFlow-Windows.zip", f"sha256:{digest}", "", "",
    )
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(update_service.urllib.request, "urlopen", lambda *_args, **_kwargs: Response(content))
    result = update_service.download_update(info)
    assert result.read_bytes() == content


def test_update_check_reports_network_or_private_repository(monkeypatch):
    monkeypatch.setattr(
        update_service.urllib.request, "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(urllib.error.HTTPError("", 404, "", {}, None)),
    )
    with pytest.raises(update_service.UpdateCheckError):
        update_service.check_for_update()
