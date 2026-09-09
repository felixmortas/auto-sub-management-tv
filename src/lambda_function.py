import json
import logging
import os

from core.logic import EnrollmentLogic
from core.parser import HelloAssoParser
from services.excel_manager import ExcelManager
from services.outlook_service import OutlookService

logger = logging.getLogger(__name__)
# Sur AWS, on garde le niveau INFO par défaut
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    try:
        if event.get('headers', {}).get('make-trigger-api-key') != os.environ['MAKE_TRIGGER_API_KEY']:
            return {'statusCode': 403, 'body': 'Mauvaise clé API depuis Make.com'}

        # 1. Récupération des données envoyées par Power Automate
        email_body = event.get('body', "")
        if not email_body:
            return {'statusCode': 400, 'body': "Corps de l'email manquant"}

        # 2. Initialisation de l'API LLM pour le parsing
        vercel_key = os.environ["AI_GATEWAY_API_KEY"]
        creds_json = json.loads(os.environ['GOOGLE_CREDS'])
        
        spreadsheet_id = os.environ['GOOGLE_SPREADSHEET_ID']
        excel_mgr = ExcelManager(spreadsheet_id, creds_json)

        outlook_service = OutlookService(
            client_id=os.environ["OUTLOOK_CLIENT_ID"],
            client_secret=os.environ["OUTLOOK_CLIENT_SECRET"],
            refresh_token=os.environ["OUTLOOK_REFRESH_TOKEN"]
        )
        outlook_service.validate_connection()

        # 3. Exécution de la logique métier
        parsed_data = HelloAssoParser.parse_email(email_body, vercel_key)
        logger.info("Données extraites : %s", parsed_data)

        logic = EnrollmentLogic(excel_mgr, outlook_service=outlook_service)
        for item in parsed_data:
            logic.process(item)

        return {
            'statusCode': 200,
            'body': json.dumps([
                f"Adhésion de {item['first_name']} traitée avec succès."
                for item in parsed_data
            ])
        }

    except Exception as e:
        logger.exception("Erreur détaillée pendant le traitement de la Lambda")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Erreur interne : {e!s}")
        }