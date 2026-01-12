import requests

class OutlookService:
    def __init__(self, client_id, client_secret, refresh_token, tenant_id="common"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self.send_url = "https://graph.microsoft.com/v1.0/me/sendMail"

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

    def send_plot_notification(self, recipient_email, first_name, plot_number):
        print(f"🔵 Envoi notification Email à {recipient_email} pour la parcelle {plot_number}")
        access_token = self._get_access_token()
        
        email_content = {
            "message": {
                "subject": "Votre numéro de parcelle - Toits Vivants",
                "body": {
                    "contentType": "Text",
                    "content": f"Bonjour {first_name},\n\nNous avons le plaisir de vous confirmer l'attribution de votre parcelle numéro : {plot_number}.\n\nVous pouvez localiser votre parcelle à l'aide du plan du toit accessible à ce lien : https://drive.google.com/file/d/14hi1-49npN0gIMNMV_SRU4CwWNVXj6sh/view?usp=sharing\n\nSi vous n'êtes pas encore sur le groupe WhatsApp, n'hésitez pas à le rejoindre en cliquant sur ce lien : https://chat.whatsapp.com/0ocnGSKpLdu0f0vgfnHAzK\n\nCordialement,\nL'équipe de l'association."
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