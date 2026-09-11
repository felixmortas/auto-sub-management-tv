import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Charge les variables d'environnement avant d'importer le handler
load_dotenv()

from lambda_function import lambda_handler

# Chemin vers tes données de test
SCENARIOS_DIR = Path(__file__).parent / "data"

@pytest.fixture
def mock_event():
    """Génère un faux event d'API Gateway contenant l'email de test."""
    scenario_path = SCENARIOS_DIR / "email_test.html"
    if not scenario_path.exists():
        pytest.fail(f"Le fichier de test {scenario_path} est introuvable.")
        
    email_content = scenario_path.read_text(encoding="utf-8")
    
    return {
        "headers": {
            "make-trigger-api-key": os.environ["MAKE_TRIGGER_API_KEY"]
        },
        "body": email_content,
    }

def test_lambda_end_to_end(mock_event, monkeypatch):
    """
    Test End-to-End : 
    - Parse le vrai email avec le vrai LLM
    - Écrit dans le Google Sheet de test
    - Envoie un vrai email via Outlook
    """
    # 1. On s'assure d'avoir l'ID du Google Sheet de test dans le .env
    test_spreadsheet_id = os.environ.get("GOOGLE_SPREADSHEET_ID")
    if not test_spreadsheet_id:
        pytest.fail("GOOGLE_SPREADSHEET_ID manquant dans le fichier .env")
        
    # 2. Exécution de la Lambda
    response = lambda_handler(mock_event, context=None)

    # 3. Assertions de base
    assert response['statusCode'] == 200
    
    body = json.loads(response['body'])
    assert isinstance(body, list)
    assert len(body) > 0
    assert "traitée avec succès" in body[0]