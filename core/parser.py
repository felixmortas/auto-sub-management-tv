import os
import json
import requests 

class HelloAssoParser:
    @staticmethod
    def parse_email(email_content):
        api_key = os.environ["MISTRAL_API_KEY"]
        model = "mistral-small-latest"
        url = "https://api.mistral.ai/v1/chat/completions"
        
        # 1. Chargement du prompt
        # On suppose que le dossier 'prompts' est à la racine du projet
        prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'email_parser.md')
        with open(prompt_path, 'r', encoding='utf-8') as f:
            system_prompt = f.read()

        # 2. Préparation de la requête
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Contenu de l'email à parser :\n\n{email_content}"}
            ],
            "response_format": {"type": "json_object"} # Force le format JSON
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # 3. Conversion de la chaîne JSON en dictionnaire Python
            parsed_data = json.loads(content)
            
            # Sécurité : On s'assure que les booléens sont corrects pour Excel
            # (Certains LLM peuvent renvoyer des strings "true" au lieu de booleens)
            if isinstance(parsed_data.get('has_plot'), str):
                parsed_data['has_plot'] = parsed_data['has_plot'].lower() == 'true'

            return parsed_data

        except Exception as e:
            print(f"Erreur lors du parsing LLM : {e}")
            # Fallback ou remontée de l'erreur selon votre besoin
            raise e

'''
# Old parser implementation using regex

import re
from datetime import datetime

class HelloAssoParser:
    @staticmethod
    def parse_email(email_content):
        # Nettoyage initial
        content = email_content.replace('\xa0', ' ').replace('\u2028', ' ')
        
        parser = HelloAssoParser
        return {
            "year": parser._extract_year(content),
            "date": parser._extract_date(content),
            "first_name": parser._extract_identity(content)['first_name'],
            "last_name": parser._extract_identity(content)['last_name'],
            "email": parser._extract_member_email(content),
            'phone': parser._extract_phone(content),
            "has_plot": parser._extract_has_plot(content),
            "membership_type": parser._extract_membership_type(content)
        }

    @staticmethod
    def _extract_year(content):
        match = re.search(r"Adhésion association Toits Vivants (\d{4})", content)
        return match.group(1) if match else str(datetime.now().year)

    @staticmethod
    def _extract_date(content):
        # On cherche la date après le numéro de commande
        match = re.search(r"Commande n°\d+ - (\d{1,2}\s+[a-zéû.]+\s+\d{4})", content)
        if not match:
            return datetime.now().strftime("%d/%m/%Y")
        
        raw_date = match.group(1).lower()
        
        # Dictionnaire pour convertir les mois français
        months = {
            'janv.': '01', 'févr.': '02', 'mars': '03', 'avr.': '04', 
            'mai': '05', 'juin': '06', 'juil.': '07', 'août': '08', 
            'sept.': '09', 'oct.': '10', 'nov.': '11', 'déc.': '12'
        }
        
        try:
            parts = raw_date.split() # ['6', 'janv.', '2026']
            day = parts[0].zfill(2)
            month = months.get(parts[1], "01")
            year = parts[2]
            return f"{day}/{month}/{year}"
        except Exception:
            return datetime.now().strftime("%d/%m/%Y")

    @staticmethod
    def _extract_identity(content):
        # On capture la ligne juste après "Payé par"
        match = re.search(r"Payé par\n\s*(.+)", content)
        if match:
            full_name = match.group(1).strip()
            parts = full_name.split(' ', 1)
            return {
                "first_name": parts[0] if len(parts) > 0 else "",
                "last_name": parts[1] if len(parts) > 1 else "A COMPLETER"
            }
        return {"first_name": "Inconnu", "last_name": "Inconnu"}

    @staticmethod
    def _extract_member_email(content):
        # Stratégie : capturer l'email qui se trouve juste après le nom de l'acheteur
        # On cherche un pattern d'email qui ne soit PAS contact@helloasso.com
        emails = re.findall(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", content)
        
        for email in emails:
            if "helloasso" not in email.lower() and "toitsvivants" not in email.lower():
                return email.strip()
        return "non-trouve@test.com"
    
    @staticmethod
    def _extract_phone(content):
        # A tester à partir du nouveau formulaire AlloAsso
        match = re.search(r"Tél[:\s]+([\d\s.+-]{6,})", content)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_has_plot(content):
        return "Mise à disposition d'une parcelle" in content

    @staticmethod
    def _extract_membership_type(content):
        if "Adhésion Individuelle" in content:
            return "Individuelle"
        elif "Adhésion Familiale" in content:
            return "Familiale"
        return "Indéterminé"
'''