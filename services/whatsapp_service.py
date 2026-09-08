import logging

import requests
import json

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self, token, phone_number_id):
        self.url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def send_plot_notification(self, recipient_phone, first_name, plot_number):
        """
        Envoie un message via un modèle (Template) validé par Meta.
        """
        logger.debug("🟢 Envoi notification WhatsApp à %s pour la parcelle %s", recipient_phone, plot_number)
        data = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "template",
            "template": {
                "name": "notification_parcelle", # Nom du template validé
                "language": { "code": "fr" },
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": first_name},
                            {"type": "text", "text": plot_number}
                        ]
                    }
                ]
            }
        }
        try:
            response = requests.post(self.url, headers=self.headers, data=json.dumps(data))
            logger.debug("✅ Message envoyé, réponse: %s - %s", response.status_code, response.text)
            return response.json()
        except Exception as e:
            logger.debug("❌ Erreur lors de l'envoi du message WhatsApp: %s", e)
            return None