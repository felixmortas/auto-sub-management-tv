import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

class Judge:
    @staticmethod
    def check_names(full_name, members_names, api_key):
        model = "deepseek/deepseek-v4-flash-0731"
        url = "https://ai-gateway.vercel.sh/v1/chat/completions"
        
        # 1. Chargement du prompt
        # On suppose que le dossier 'prompts' est à la racine du projet
        prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'names_similarity_judge.md')
        with open(prompt_path, 'r', encoding='utf-8') as f:
            system_prompt = f.read()

        # 2. Préparation de la requête
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Nom complet à comparer : {full_name}\n\nNoms des membres de l'année précédente :\n{members_names}"}
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
            if isinstance(parsed_data.get('similarity_found'), str):
                parsed_data['similarity_found'] = parsed_data['similarity_found'].lower() == 'true'

            return parsed_data

        except Exception as e:
            logger.debug("❌ Erreur lors du parsing LLM : %s", e)
            # Fallback ou remontée de l'erreur selon votre besoin
            raise