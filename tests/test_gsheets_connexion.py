import gspread
from google.oauth2.service_account import Credentials

# Configuration
SERVICE_ACCOUNT_FILE = 'auto-sub-management-tv-cf8b4c7b9ab7.json' # Votre fichier téléchargé
SPREADSHEET_ID = '15OLd9RvqXzllTTzuNCnHvkfjuzjyYpWfo35nvgfZ63A'    # Trouvé dans l'URL du Google Sheet

def test_google_connection():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
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

if __name__ == "__main__":
    test_google_connection()