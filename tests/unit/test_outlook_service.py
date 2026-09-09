"""
Unit tests for OutlookService.

Run with:
    pytest test_outlook_service.py -v

All HTTP calls (token retrieval + email sending) are mocked, and templates
are written to a temporary directory so tests never touch the network or
the real filesystem.
"""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from services.outlook_service import OutlookService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def service(tmp_path):
    """Return an OutlookService instance pointed at a temp templates dir."""
    return OutlookService(
        client_id="fake-client-id",
        client_secret="fake-client-secret",
        refresh_token="fake-refresh-token",
        tenant_id="fake-tenant",
        templates_dir=str(tmp_path),
    )


def make_response(status_code=200, json_data=None, text=""):
    """Build a fake requests.Response-like object."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = status_code
    mock_response.text = text
    mock_response.json.return_value = json_data or {}

    def raise_for_status():
        if status_code >= 400:
            raise requests.HTTPError(f"HTTP {status_code}")

    mock_response.raise_for_status.side_effect = raise_for_status
    return mock_response


# ---------------------------------------------------------------------------
# _get_access_token
# ---------------------------------------------------------------------------

class TestGetAccessToken:

    @patch("services.outlook_service.requests.post")
    def test_fetches_new_token_when_no_cache(self, mock_post, service):
        mock_post.return_value = make_response(
            status_code=200,
            json_data={"access_token": "token-abc", "expires_in": 3600},
        )

        token = service._get_access_token()

        assert token == "token-abc"
        mock_post.assert_called_once_with(
            service.token_url,
            data={
                "client_id": "fake-client-id",
                "scope": "https://graph.microsoft.com/Mail.Send offline_access",
                "refresh_token": "fake-refresh-token",
                "grant_type": "refresh_token",
                "client_secret": "fake-client-secret",
            },
        )

    @patch("services.outlook_service.requests.post")
    def test_uses_cached_token_when_still_valid(self, mock_post, service):
        service._access_token = "cached-token"
        service._access_token_expires_at = time.time() + 3600  # far in the future

        token = service._get_access_token()

        assert token == "cached-token"
        mock_post.assert_not_called()

    @patch("services.outlook_service.requests.post")
    def test_refreshes_when_token_close_to_expiry(self, mock_post, service):
        # Token expires in 30s, which is under the 60s safety margin.
        service._access_token = "stale-token"
        service._access_token_expires_at = time.time() + 30

        mock_post.return_value = make_response(
            status_code=200,
            json_data={"access_token": "fresh-token", "expires_in": 3600},
        )

        token = service._get_access_token()

        assert token == "fresh-token"
        mock_post.assert_called_once()

    @patch("services.outlook_service.requests.post")
    def test_raises_when_no_access_token_in_response(self, mock_post, service):
        mock_post.return_value = make_response(
            status_code=200,
            json_data={"error": "invalid_grant"},
        )

        with pytest.raises(RuntimeError, match="Unable to retrieve access token"):
            service._get_access_token()

    @patch("services.outlook_service.requests.post")
    def test_raises_on_http_error(self, mock_post, service):
        mock_post.return_value = make_response(status_code=400, text="Bad Request")

        with pytest.raises(requests.HTTPError):
            service._get_access_token()

    @patch("services.outlook_service.requests.post")
    def test_rotates_refresh_token_when_provided(self, mock_post, service):
        mock_post.return_value = make_response(
            status_code=200,
            json_data={
                "access_token": "token-abc",
                "expires_in": 3600,
                "refresh_token": "new-refresh-token",
            },
        )

        service._get_access_token()

        assert service.refresh_token == "new-refresh-token"

    @patch("services.outlook_service.requests.post")
    def test_keeps_old_refresh_token_when_not_rotated(self, mock_post, service):
        mock_post.return_value = make_response(
            status_code=200,
            json_data={"access_token": "token-abc", "expires_in": 3600},
        )

        service._get_access_token()

        assert service.refresh_token == "fake-refresh-token"


# ---------------------------------------------------------------------------
# _load_template
# ---------------------------------------------------------------------------

class TestLoadTemplate:

    def test_loads_and_formats_template(self, service, tmp_path):
        template_file = tmp_path / "hello.html"
        template_file.write_text(
            "<p>Hello {first_name}, your plot is {plot_number}</p>",
            encoding="utf-8",
        )

        result = service._load_template(
            "hello.html", first_name="Alice", plot_number=42
        )

        assert result == "<p>Hello Alice, your plot is 42</p>"

    def test_raises_file_not_found_when_template_missing(self, service):
        with pytest.raises(FileNotFoundError, match="Template not found"):
            service._load_template("does_not_exist.html")


# ---------------------------------------------------------------------------
# _send_email
# ---------------------------------------------------------------------------

class TestSendEmail:

    @patch("services.outlook_service.requests.post")
    @patch.object(OutlookService, "_get_access_token", return_value="fake-token")
    def test_returns_true_on_202(self, mock_get_token, mock_post, service):
        mock_post.return_value = make_response(status_code=202)

        result = service._send_email(
            recipient_email="test@example.com",
            subject="Subject",
            html_content="<p>Body</p>",
        )

        assert result is True
        mock_post.assert_called_once_with(
            service.send_url,
            headers={
                "Authorization": "Bearer fake-token",
                "Content-Type": "application/json",
            },
            json={
                "message": {
                    "subject": "Subject",
                    "body": {"contentType": "HTML", "content": "<p>Body</p>"},
                    "toRecipients": [
                        {"emailAddress": {"address": "test@example.com"}}
                    ],
                }
            },
        )

    @patch("services.outlook_service.requests.post")
    @patch.object(OutlookService, "_get_access_token", return_value="fake-token")
    def test_returns_false_on_non_202(self, mock_get_token, mock_post, service):
        mock_post.return_value = make_response(
            status_code=500, text="Internal Server Error"
        )

        result = service._send_email(
            recipient_email="test@example.com",
            subject="Subject",
            html_content="<p>Body</p>",
        )

        assert result is False

    @patch("services.outlook_service.requests.post")
    @patch.object(OutlookService, "_get_access_token", return_value="fake-token")
    def test_returns_false_on_network_error(self, mock_get_token, mock_post, service):
        mock_post.side_effect = requests.RequestException("connection failed")

        result = service._send_email(
            recipient_email="test@example.com",
            subject="Subject",
            html_content="<p>Body</p>",
        )

        assert result is False


# ---------------------------------------------------------------------------
# send_plot_notification / send_new_sub_notification
# (tested as pure orchestration: internal calls are mocked out)
# ---------------------------------------------------------------------------

class TestSendPlotNotification:

    @patch.object(OutlookService, "_send_email", return_value=True)
    @patch.object(OutlookService, "_load_template", return_value="<p>rendered</p>")
    def test_calls_load_template_and_send_email_with_correct_args(
        self, mock_load_template, mock_send_email, service
    ):
        result = service.send_plot_notification(
            recipient_email="alice@example.com",
            first_name="Alice",
            plot_number=7,
        )

        assert result is True
        mock_load_template.assert_called_once_with(
            "plot_notification.html", first_name="Alice", plot_number=7
        )
        mock_send_email.assert_called_once_with(
            recipient_email="alice@example.com",
            subject="Votre numéro de parcelle - Toits Vivants",
            html_content="<p>rendered</p>",
        )

    @patch.object(OutlookService, "_send_email", return_value=False)
    @patch.object(OutlookService, "_load_template", return_value="<p>rendered</p>")
    def test_propagates_failure_from_send_email(
        self, mock_load_template, mock_send_email, service
    ):
        result = service.send_plot_notification(
            recipient_email="alice@example.com",
            first_name="Alice",
            plot_number=7,
        )

        assert result is False


class TestSendNewSubNotification:

    @patch.object(OutlookService, "_send_email", return_value=True)
    @patch.object(OutlookService, "_load_template", return_value="<p>welcome</p>")
    def test_calls_load_template_and_send_email_with_correct_args(
        self, mock_load_template, mock_send_email, service
    ):
        result = service.send_new_sub_notification(
            recipient_email="bob@example.com",
            first_name="Bob",
        )

        assert result is True
        mock_load_template.assert_called_once_with(
            "new_subscription.html", first_name="Bob"
        )
        mock_send_email.assert_called_once_with(
            recipient_email="bob@example.com",
            subject="Bienvenue chez Toits Vivants !",
            html_content="<p>welcome</p>",
        )
