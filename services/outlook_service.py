import requests
from pathlib import Path

class OutlookService:
    def __init__(self, client_id, client_secret, refresh_token, tenant_id="common", templates_dir="email_templates"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self.send_url = "https://graph.microsoft.com/v1.0/me/sendMail"
        self.templates_dir = Path(templates_dir)

    def _get_access_token(self):
        data = {
            "client_id": self.client_id,
            "scope": "https://graph.microsoft.com/Mail.Send offline_access",
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
            "client_secret": self.client_secret,
        }
        response = requests.post(self.token_url, data=data)
        res_json = response.json()
        
        token = res_json.get("access_token")
        if not token:
            raise Exception(f"Impossible de récupérer l'access_token: {res_json}")
        return token
    
    def _load_template(self, template_name, **kwargs):
        """Charge un template HTML et remplace les variables."""
        template_path = self.templates_dir / template_name
        
        if not template_path.exists():
            raise FileNotFoundError(f"Template non trouvé: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Remplace les variables dans le template
        return template_content.format(**kwargs)


    def send_plot_notification(self, recipient_email, first_name, plot_number):
        print(f"🔵 Envoi notification Email à {recipient_email} pour la parcelle {plot_number}")
        access_token = self._get_access_token()

        html_content = self._load_template(
            "plot_notification.html",
            first_name=first_name,
            plot_number=plot_number
        )

        
        email_content = {
            "message": {
                "subject": "Votre numéro de parcelle - Toits Vivants",
                "body": {
                    "contentType": "HTML",
                    "content": html_content
                },
                "toRecipients": [{"emailAddress": {"address": recipient_email}}]
            }
        }

        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        response = requests.post(self.send_url, headers=headers, json=email_content)
        
        if response.status_code == 202:
            print("✅ Email envoyé avec succès.")
            return True
        else:
            print(f"❌ Erreur email: {response.text}")
            return False
        
    def send_new_sub_notification(self, recipient_email, first_name):
        print(f"🔵 Envoi notification Email à {recipient_email} pour nouvelle adhésion")
        access_token = self._get_access_token()

        html_content = self._load_template(
            "new_subscription.html",
            first_name=first_name
        )
        
        email_content = {
            "message": {
                "subject": "Bienvenue chez Toits Vivants !",
                "body": {
                    "contentType": "HTML",
                    "content": html_content
                },
                "toRecipients": [{"emailAddress": {"address": recipient_email}}]
            }
        }

        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        response = requests.post(self.send_url, headers=headers, json=email_content)
        
        if response.status_code == 202:
            print("✅ Email envoyé avec succès.")
            return True
        else:
            print(f"❌ Erreur email: {response.text}")
            return False