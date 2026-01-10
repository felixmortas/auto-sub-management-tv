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