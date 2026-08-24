import requests
import os
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv
load_dotenv()

# CONFIGURATION
CLIENT_ID = os.environ["OUTLOOK_CLIENT_ID"]
CLIENT_SECRET = os.environ["OUTLOOK_CLIENT_SECRET"]
REDIRECT_URI = "http://localhost"
SCOPE = "https://graph.microsoft.com/Mail.Send offline_access"


def get_tokens():
    # 1. Générer l'URL d'autorisation pour l'utilisateur
    auth_url = (
        f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_mode=query"
        f"&scope={SCOPE}"
    )

    print("--- ÉTAPE 1 ---")
    print(f"Copiez cette URL dans votre navigateur :\n\n{auth_url}\n")
    print("--- ÉTAPE 2 ---")
    print("Connectez-vous. Vous allez arriver sur une page d'erreur (localhost).")
    print("⚠️  Faites vite : le code expire en quelques minutes et n'est utilisable qu'une seule fois.")
    full_callback_url = input(
        "Copiez ici l'URL complète de la barre d'adresse "
        "(celle qui commence par http://localhost/?code=...) : "
    )

    # Proper parsing + URL-decoding of the query string, instead of a raw string split.
    # Authorization codes often contain characters like +, /, =, $ which appear
    # percent-encoded (%2B, %2F, %3D, %24...) in the browser address bar.
    parsed_url = urlparse(full_callback_url)
    query_params = parse_qs(parsed_url.query)

    if "code" not in query_params:
        print("❌ Code introuvable dans l'URL fournie.")
        if "error" in query_params:
            print(f"Erreur retournée par Microsoft : {query_params.get('error_description')}")
        return

    code = query_params["code"][0]

    # 2. Échange du code contre les jetons
    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    data = {
        "client_id": CLIENT_ID,
        "scope": SCOPE,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
        "client_secret": CLIENT_SECRET,
    }

    print("\n--- ÉTAPE 3 ---")
    print("Échange du code contre le Refresh Token...")

    response = requests.post(token_url, data=data)
    res_data = response.json()

    if "refresh_token" in res_data:
        print("\n✅ SUCCÈS !")
        print(f"Votre REFRESH_TOKEN :\n\n{res_data['refresh_token']}\n")
        print("Sauvegardez ce jeton précieusement dans vos variables d'environnement AWS Lambda.")
    else:
        print("\n❌ ERREUR lors de l'échange :")
        print(response.text)


if __name__ == "__main__":
    get_tokens()