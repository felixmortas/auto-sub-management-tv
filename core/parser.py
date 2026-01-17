import os
import json
import requests 

class HelloAssoParser:
    @staticmethod
    def parse_email(email_content, api_key):
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

            adhesions_list = parsed_data.get("adhesions", [])
            
            # Sécurité : On s'assure que les booléens sont corrects pour Excel
            # (Certains LLM peuvent renvoyer des strings "true" au lieu de booleens)
            for item in adhesions_list:
                if isinstance(item.get('has_plot'), str):
                    item['has_plot'] = item['has_plot'].lower() == 'true'

            return adhesions_list

        except Exception as e:
            print(f"Erreur lors du parsing LLM : {e}")
            # Fallback ou remontée de l'erreur selon votre besoin
            raise e