import logging
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


class OutlookService:
    def __init__(
        self,
        client_id,
        client_secret,
        refresh_token,
        tenant_id="common",
        templates_dir="email_templates"
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token

        self.token_url = (
            f"https://login.microsoftonline.com/"
            f"{tenant_id}/oauth2/v2.0/token"
        )
        self.send_url = "https://graph.microsoft.com/v1.0/me/sendMail"
        self.templates_dir = Path(templates_dir)

        # Cache the access token to avoid requesting a new one
        # for every email sent.
        self._access_token = None
        self._access_token_expires_at = 0

    def _get_access_token(self):
        """Return a valid access token, refreshing it only when necessary."""

        # Reuse the cached token if it is still valid.
        # A 60-second safety margin prevents using a token
        # that is about to expire.
        if (
            self._access_token
            and time.time() < self._access_token_expires_at - 60
        ):
            return self._access_token

        data = {
            "client_id": self.client_id,
            "scope": "https://graph.microsoft.com/Mail.Send offline_access",
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
            "client_secret": self.client_secret,
        }

        response = requests.post(
            self.token_url,
            data=data,
        )

        # Raise an exception for HTTP errors such as 400, 401, 500, etc.
        response.raise_for_status()

        res_json = response.json()

        access_token = res_json.get("access_token")
        if not access_token:
            raise RuntimeError(
                f"Unable to retrieve access token: {res_json}"
            )

        # Microsoft usually returns the token lifetime in seconds.
        expires_in = res_json.get("expires_in", 3600)

        self._access_token = access_token
        self._access_token_expires_at = time.time() + expires_in

        # Microsoft may rotate the refresh token.
        # Always keep the newest one when provided.
        new_refresh_token = res_json.get("refresh_token")
        if new_refresh_token:
            self.refresh_token = new_refresh_token

        return self._access_token

    def _load_template(self, template_name, **kwargs):
        """Load an HTML template and replace its variables."""

        template_path = self.templates_dir / template_name

        if not template_path.exists():
            raise FileNotFoundError(
                f"Template not found: {template_path}"
            )

        with open(template_path, "r", encoding="utf-8") as file:
            template_content = file.read()

        # Replace template placeholders with the provided values.
        return template_content.format(**kwargs)

    def _send_email(self, recipient_email, subject, html_content):
        """Send an HTML email through Microsoft Graph."""

        access_token = self._get_access_token()

        email_content = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": html_content,
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": recipient_email
                        }
                    }
                ],
            }
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self.send_url,
                headers=headers,
                json=email_content,
            )
        except requests.RequestException:
            logger.exception(
                "❌ Network error while sending email to %s",
                recipient_email
            )
            return False

        if response.status_code == 202:
            logger.debug(
                "✅ Email successfully sent to %s.",
                recipient_email
            )
            return True

        logger.error(
            "❌ Failed to send email to %s. HTTP %s: %s",
            recipient_email,
            response.status_code,
            response.text
        )
        return False

    def validate_connection(self):
        """
        Validate that Outlook authentication is working.

        This forces the retrieval of an access token so that authentication
        errors occur before the business process starts.
        """
        logger.debug("🔵 Validating Outlook connection...")

        self._get_access_token()

    logger.debug("✅ Outlook authentication successful.")

    def send_plot_notification(
        self,
        recipient_email,
        first_name,
        plot_number
    ):
        """Send the plot number notification email."""

        logger.debug(
            "🔵 Sending plot notification email to %s for plot %s",
            recipient_email,
            plot_number
        )

        html_content = self._load_template(
            "plot_notification.html",
            first_name=first_name,
            plot_number=plot_number
        )

        return self._send_email(
            recipient_email=recipient_email,
            subject="Votre numéro de parcelle - Toits Vivants",
            html_content=html_content
        )

    def send_new_sub_notification(
        self,
        recipient_email,
        first_name
    ):
        """Send the new subscription welcome email."""

        logger.debug(
            "🔵 Sending new subscription email to %s",
            recipient_email
        )

        html_content = self._load_template(
            "new_subscription.html",
            first_name=first_name
        )

        return self._send_email(
            recipient_email=recipient_email,
            subject="Bienvenue chez Toits Vivants !",
            html_content=html_content
        )