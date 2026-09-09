import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Détecte un lancement local : soit sous debugger (VS Code / debugpy),
# soit une exécution directe du fichier (python lambda_function.py).
# Sur AWS, ce module est importé -> __name__ != "__main__" et pas de debugger.
IS_LOCAL_DEBUG = sys.gettrace() is not None or __name__ == "__main__"

# En local sous debugger uniquement, charge les variables du fichier .env
# Ce bloc est volontairement placé AVANT les imports de l'application.
if IS_LOCAL_DEBUG:
    from dotenv import load_dotenv
    load_dotenv()

# Configuration globale du logging, une seule fois au point d'entrée.
LOG_LEVEL = logging.DEBUG if IS_LOCAL_DEBUG else logging.INFO
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
# AWS Lambda peut avoir déjà installé un handler sur le root logger.
# On force donc explicitement son niveau.
logging.getLogger().setLevel(LOG_LEVEL)

logger = logging.getLogger(__name__)

from core.parser import HelloAssoParser
from core.logic import EnrollmentLogic
from services.excel_manager import ExcelManager
from services.whatsapp_service import WhatsAppService
from services.outlook_service import OutlookService


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

        # 3. Initialisation du gestionnaire Excel
        # En local debug, GOOGLE_CREDS peut venir du .env.
        # En production, il vient des variables d'environnement Lambda.
        creds_json = json.loads(os.environ['GOOGLE_CREDS'])

        spreadsheet_id = "15OLd9RvqXzllTTzuNCnHvkfjuzjyYpWfo35nvgfZ63A"
        excel_mgr = ExcelManager(spreadsheet_id, creds_json)

        # 4. Initialisation du service WhatsApp
        # whatsapp_token = os.environ["WHATSAPP_TOKEN"]
        # phone_number_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
        # whatsapp_service = WhatsAppService(whatsapp_token, phone_number_id)

        # 5. Initialisation du service Outlook
        outlook_service = OutlookService(
            client_id=os.environ["OUTLOOK_CLIENT_ID"],
            client_secret=os.environ["OUTLOOK_CLIENT_SECRET"],
            refresh_token=os.environ["OUTLOOK_REFRESH_TOKEN"]
        )

        # Fail early if Outlook authentication is no longer valid.
        outlook_service.validate_connection()

        # 6. Exécution de la logique métier
        parsed_data = HelloAssoParser.parse_email(email_body, vercel_key)
        logger.debug("Données extraites : %s", parsed_data)

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
        # Les erreurs inattendues restent visibles en production.
        logger.exception("Erreur détaillée pendant le traitement de la Lambda")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Erreur interne : {str(e)}")
        }


# --------------------------------------------------------------------------- #
# Local simulation.
# This whole section only runs when the file is executed directly
# (e.g. via a debugger), never when AWS Lambda imports this module.
# --------------------------------------------------------------------------- #

# Folder holding one .txt file per test scenario. Adding a new scenario is
# just a matter of dropping a new .txt file here, no code change needed.
SCENARIOS_DIR = Path(__file__).parent / "tests" / "data"
DEFAULT_SCENARIO = "email_test"


def _list_scenarios() -> list[str]:
    """Return the names (without extension) of all available scenarios."""
    if not SCENARIOS_DIR.exists():
        return []
    return sorted(p.stem for p in SCENARIOS_DIR.glob("*.txt"))


def _load_scenario(scenario_name: str) -> str:
    """Load the raw email content for a given scenario name."""
    scenario_path = SCENARIOS_DIR / f"{scenario_name}.txt"
    if not scenario_path.exists():
        available = ", ".join(_list_scenarios()) or "(aucun scénario trouvé)"
        raise FileNotFoundError(
            f"Scénario '{scenario_name}' introuvable ({scenario_path}).\n"
            f"Scénarios disponibles : {available}"
        )
    return scenario_path.read_text(encoding="utf-8")


def _build_mock_event(email_content: str) -> dict:
    """Build a fake API Gateway / Power Automate event, as used in production."""
    return {
        "headers": {
            "make-trigger-api-key": os.environ["MAKE_TRIGGER_API_KEY"]
        },
        "body": email_content,
    }


def _run_local_simulation() -> None:
    """Parse CLI args, load the chosen scenario, and invoke lambda_handler locally."""
    parser = argparse.ArgumentParser(
        description="Simule un appel Lambda en local à partir d'un scénario d'email."
    )
    parser.add_argument(
        "scenario",
        nargs="?",
        default=DEFAULT_SCENARIO,
        help=f"Nom du scénario à jouer (défaut : '{DEFAULT_SCENARIO}').",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Liste les scénarios disponibles et quitte.",
    )
    args = parser.parse_args()

    if args.list:
        scenarios = _list_scenarios()
        if scenarios:
            print("Scénarios disponibles :")
            for name in scenarios:
                print(f"  - {name}")
        else:
            print(f"Aucun scénario trouvé dans {SCENARIOS_DIR}")
        return

    print(f"--- Simulation locale : scénario '{args.scenario}' ---")
    email_content = _load_scenario(args.scenario)
    mock_event = _build_mock_event(email_content)

    response = lambda_handler(mock_event, None)

    print("--- Simulation terminée ---")
    print(f"Réponse de la Lambda : {response}")


if __name__ == "__main__":
    _run_local_simulation()