"""
Integration tests for OutlookService.

Unlike the unit tests, these hit the REAL Microsoft identity platform and
Microsoft Graph API. They require valid credentials and will actually send
emails, so they are opt-in only.

Setup:
    Export the following environment variables before running:
        OUTLOOK_CLIENT_ID
        OUTLOOK_CLIENT_SECRET
        OUTLOOK_REFRESH_TOKEN
        OUTLOOK_TEST_RECIPIENT   # a mailbox you control, safe to spam
        OUTLOOK_TENANT_ID        # optional, defaults to "common"

Run with:
    pytest -m integration test_outlook_service_integration.py -v

These tests are skipped automatically when the credentials are missing, so
they never break a regular CI run (`pytest -m "not integration"`).
"""

import os

import pytest
import requests

from services.outlook_service import OutlookService

# ---------------------------------------------------------------------------
# Skip condition: only run if real credentials are provided via env vars.
# ---------------------------------------------------------------------------

REQUIRED_ENV_VARS = [
    "OUTLOOK_CLIENT_ID",
    "OUTLOOK_CLIENT_SECRET",
    "OUTLOOK_REFRESH_TOKEN",
    "OUTLOOK_TEST_RECIPIENT",
]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        bool(missing_vars),
        reason=(
            "Missing environment variables for integration tests: "
            f"{', '.join(missing_vars)}"
        ),
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_service(tmp_path_factory):
    """
    Build a real OutlookService pointed at the actual Microsoft endpoints.

    Templates live in a throwaway temp directory since we only want to
    exercise the network path here, not the HTML rendering logic
    (already covered by unit tests).
    """
    templates_dir = tmp_path_factory.mktemp("integration_templates")

    (templates_dir / "plot_notification.html").write_text(
        "<p>[TEST] Hello {first_name}, your plot number is {plot_number}.</p>",
        encoding="utf-8",
    )
    (templates_dir / "new_subscription.html").write_text(
        "<p>[TEST] Welcome {first_name}!</p>",
        encoding="utf-8",
    )

    return OutlookService(
        client_id=os.environ["OUTLOOK_CLIENT_ID"],
        client_secret=os.environ["OUTLOOK_CLIENT_SECRET"],
        refresh_token=os.environ["OUTLOOK_REFRESH_TOKEN"],
        tenant_id=os.environ.get("OUTLOOK_TENANT_ID", "common"),
        templates_dir=str(templates_dir),
    )


@pytest.fixture(scope="module")
def test_recipient():
    return os.environ["OUTLOOK_TEST_RECIPIENT"]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestRealAuthentication:

    def test_can_obtain_a_real_access_token(self, real_service):
        """
        Validates that the client_id / client_secret / refresh_token combo
        is actually accepted by Microsoft's identity platform and that the
        required Mail.Send scope is granted.
        """
        token = real_service._get_access_token()

        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_is_cached_on_second_call(self, real_service):
        """A second call within the token lifetime should not hit the network."""
        first_token = real_service._get_access_token()
        second_token = real_service._get_access_token()

        assert first_token == second_token


# ---------------------------------------------------------------------------
# Real email sending
# ---------------------------------------------------------------------------

class TestRealEmailSending:

    def test_send_email_returns_true_for_valid_recipient(
        self, real_service, test_recipient
    ):
        """
        Sends an actual email through Microsoft Graph.
        The subject is prefixed with [TEST] so it's easy to filter/delete
        from the test mailbox.
        """
        result = real_service._send_email(
            recipient_email=test_recipient,
            subject="[TEST] OutlookService integration test",
            html_content="<p>This is an automated integration test email.</p>",
        )

        assert result is True

    def test_send_email_returns_false_for_malformed_recipient(self, real_service):
        """
        Microsoft Graph should reject an obviously invalid address,
        exercising the failure path against the real API contract.
        """
        result = real_service._send_email(
            recipient_email="not-a-valid-email-address",
            subject="[TEST] Should fail",
            html_content="<p>This should not be delivered.</p>",
        )

        assert result is False


# ---------------------------------------------------------------------------
# End-to-end public methods
# ---------------------------------------------------------------------------

class TestRealNotificationFlows:

    def test_send_plot_notification_end_to_end(self, real_service, test_recipient):
        result = real_service.send_plot_notification(
            recipient_email=test_recipient,
            first_name="Integration Test",
            plot_number=999,
        )

        assert result is True

    def test_send_new_sub_notification_end_to_end(self, real_service, test_recipient):
        result = real_service.send_new_sub_notification(
            recipient_email=test_recipient,
            first_name="Integration Test",
        )

        assert result is True


# ---------------------------------------------------------------------------
# Bad credentials (sanity check on error handling against the real API)
# ---------------------------------------------------------------------------

class TestRealAuthenticationFailure:

    def test_invalid_refresh_token_raises_http_error(self):
        """
        A garbage refresh token should be rejected by Microsoft with a
        4xx response, which _get_access_token() propagates as HTTPError.
        """
        bad_service = OutlookService(
            client_id=os.environ["OUTLOOK_CLIENT_ID"],
            client_secret=os.environ["OUTLOOK_CLIENT_SECRET"],
            refresh_token="clearly-invalid-refresh-token",
            tenant_id=os.environ.get("OUTLOOK_TENANT_ID", "common"),
        )

        with pytest.raises(requests.HTTPError):
            bad_service._get_access_token()
