import gspread
from google.oauth2.service_account import Credentials
from services.excel_manager import ExcelManager
import json

# Configuration
SERVICE_ACCOUNT_FILE = 'auto-sub-management-tv-cf8b4c7b9ab7.json' # Votre fichier téléchargé
SPREADSHEET_ID = '15OLd9RvqXzllTTzuNCnHvkfjuzjyYpWfo35nvgfZ63A'    # Trouvé dans l'URL du Google Sheet

scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def test_google_connection(scopes):
    try:
        # Authentification
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Test d'ouverture
        sh = client.open_by_key(SPREADSHEET_ID)
        print(f"✅ Connexion réussie au fichier : {sh.title}")
        
        # Liste des feuilles
        worksheets = sh.worksheets()
        print("Feuilles trouvées :", [ws.title for ws in worksheets])
        
    except Exception as e:
        print(f"❌ Erreur : {e}")

def test_members_listing(scopes):    
    try:
        # Authentification
        with open('auto-sub-management-tv-cf8b4c7b9ab7.json', 'r') as f:
            creds_json = json.load(f)
        
        excel_mgr = ExcelManager(SPREADSHEET_ID, creds_json)
        names = excel_mgr.list_members_in_sheet("2025")

        print("Noms des membres :")
        for name in names[:5]:
            print(name)
        
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des membres : {e}")

if __name__ == "__main__":
    test_google_connection(scopes)
    test_members_listing(scopes)