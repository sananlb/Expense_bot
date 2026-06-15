import io
import socket
from datetime import datetime
from datetime import timezone as dt_timezone
from urllib.error import HTTPError, URLError

import expense_bot.celery_tasks as celery_tasks
from expense_bot.celery_tasks import (
    _build_public_certificate_issue,
    _build_webhook_monitoring_issues,
    _confirm_public_monitoring_issues,
    _fetch_telegram_webhook_info,
    _get_expected_webhook_url,
    _handle_public_monitoring_issues,
)


class FakeCache:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, timeout=None):
        self.data[key] = value

    def delete(self, key):
        self.data.pop(key, None)


def test_get_expected_webhook_url_normalizes_base_and_path(monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", "https://expensebot.duckdns.org/")
    monkeypatch.setenv("WEBHOOK_PATH", "webhook/")

    assert _get_expected_webhook_url() == "https://expensebot.duckdns.org/webhook/"


def test_build_public_certificate_issue_returns_critical_before_deadline(monkeypatch):
    monkeypatch.setenv("PUBLIC_CERT_WARNING_DAYS", "21")
    monkeypatch.setenv("PUBLIC_CERT_CRITICAL_DAYS", "7")

    issue = _build_public_certificate_issue(
        cert_days_left=5,
        expires_at=datetime(2026, 7, 6, 9, 15, tzinfo=dt_timezone.utc),
        cert_error="",
    )

    assert issue is not None
    assert issue["code"] == "certificate_expiring"
    assert issue["severity"] == "critical"


def test_build_webhook_monitoring_issues_flags_recent_error_and_url_mismatch(monkeypatch):
    monkeypatch.setenv("PUBLIC_WEBHOOK_RECENT_ERROR_MINUTES", "30")
    monkeypatch.setenv("PUBLIC_WEBHOOK_PENDING_THRESHOLD", "10")
    now = datetime(2026, 4, 7, 10, 30, tzinfo=dt_timezone.utc)

    issues = _build_webhook_monitoring_issues(
        {
            "url": "https://expensebot.duckdns.org/old-webhook/",
            "pending_update_count": 14,
            "last_error_date": int(datetime(2026, 4, 7, 10, 20, tzinfo=dt_timezone.utc).timestamp()),
            "last_error_message": "SSL error: certificate verify failed",
        },
        expected_url="https://expensebot.duckdns.org/webhook/",
        now=now,
    )

    issue_codes = {issue["code"] for issue in issues}
    assert "webhook_url_mismatch" in issue_codes
    assert "webhook_pending_updates" in issue_codes
    assert "recent_webhook_error" in issue_codes


def test_build_webhook_monitoring_issues_ignores_stale_error(monkeypatch):
    monkeypatch.setenv("PUBLIC_WEBHOOK_RECENT_ERROR_MINUTES", "15")
    now = datetime(2026, 4, 7, 10, 30, tzinfo=dt_timezone.utc)

    issues = _build_webhook_monitoring_issues(
        {
            "url": "https://expensebot.duckdns.org/webhook/",
            "pending_update_count": 0,
            "last_error_date": int(datetime(2026, 4, 7, 9, 0, tzinfo=dt_timezone.utc).timestamp()),
            "last_error_message": "old error",
        },
        expected_url="https://expensebot.duckdns.org/webhook/",
        now=now,
    )

    assert all(issue["code"] != "recent_webhook_error" for issue in issues)


def test_fetch_telegram_webhook_info_retries_transient_dns_failure(monkeypatch):
    calls = []

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        if len(calls) < 3:
            raise URLError(socket.gaierror(-3, "Temporary failure in name resolution"))
        return io.BytesIO(b'{"ok": true, "result": {"url": "https://expensebot.duckdns.org/webhook/"}}')

    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.setenv("PUBLIC_WEBHOOK_REQUEST_ATTEMPTS", "3")
    monkeypatch.setenv("PUBLIC_WEBHOOK_RETRY_DELAY", "0")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    webhook_info, error = _fetch_telegram_webhook_info()

    assert error == ""
    assert webhook_info["url"] == "https://expensebot.duckdns.org/webhook/"
    assert len(calls) == 3


def test_fetch_telegram_webhook_info_does_not_retry_client_error(monkeypatch):
    calls = []

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        raise HTTPError(url, 401, "Unauthorized", {}, None)

    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.setenv("PUBLIC_WEBHOOK_REQUEST_ATTEMPTS", "3")
    monkeypatch.setenv("PUBLIC_WEBHOOK_RETRY_DELAY", "0")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    webhook_info, error = _fetch_telegram_webhook_info()

    assert webhook_info is None
    assert error == "HTTP 401"
    assert len(calls) == 1


def test_transient_monitoring_issue_requires_two_consecutive_cycles(monkeypatch):
    cache = FakeCache()
    issue = {
        "code": "webhook_info_unavailable",
        "severity": "critical",
        "message": "Не удалось получить getWebhookInfo: DNS timeout",
    }
    monkeypatch.setenv("PUBLIC_TRANSIENT_ISSUE_CONFIRMATION_CYCLES", "2")

    confirmed, pending = _confirm_public_monitoring_issues(cache, [issue])
    assert confirmed == []
    assert pending is True

    confirmed, pending = _confirm_public_monitoring_issues(cache, [issue])
    assert confirmed == [issue]
    assert pending is False

    confirmed, pending = _confirm_public_monitoring_issues(cache, [])
    assert confirmed == []
    assert pending is False
    assert cache.get(celery_tasks.CACHE_KEY_PUBLIC_ISSUE_FAILURES) is None


def test_unconfirmed_probe_failure_does_not_send_false_recovery(monkeypatch):
    cache = FakeCache()
    cache.set(celery_tasks.CACHE_KEY_PUBLIC_ISSUES_STATE, "previous-alert")
    sent_messages = []
    monkeypatch.setenv("PUBLIC_TRANSIENT_ISSUE_CONFIRMATION_CYCLES", "2")
    monkeypatch.setattr(
        celery_tasks,
        "_send_monitoring_alert",
        lambda message, label: sent_messages.append(message) or True,
    )

    _handle_public_monitoring_issues(
        cache,
        "https://expensebot.duckdns.org/health/",
        [
            {
                "code": "webhook_info_unavailable",
                "severity": "critical",
                "message": "Не удалось получить getWebhookInfo: DNS timeout",
            }
        ],
    )

    assert sent_messages == []
    assert cache.get(celery_tasks.CACHE_KEY_PUBLIC_ISSUES_STATE) == "previous-alert"
