# Toits Vivants - Membership Automation System

Ce projet automatise le processus complet d'inscription des adhérents de l'association **Toits Vivants**. Il remplace un travail manuel fastidieux par un pipeline robuste reliant HelloAsso (plateforme de paiement), Google Sheets et des services de communication, le tout en intégrant des services d'Intelligence Artificielle.

## ⚙️ Fonctionnement du Workflow

1. **Trigger :** Chaque lundi à 12h, un scénario **Make.com** filtre les emails (from: HelloAsso AND subject:"Nouvelle adhésion").
2. **Transfert :** Les corps des email sont envoyés un par un de manière sécurisée (Token Auth) à une fonction **AWS Lambda**.
3. **Analyse IA :** La Lambda utilise **Mistral AI** pour parser l'email de manière robuste et extraire les informations de l'adhésion aux formats JSON, HTML ou texte brute (les autres formats n'ont pas été testés mais devraient fonctionner). Le LLM est également utilisé pour gérer de multiples types d'erreurs de saisi des adhérents lors de la complétion du formulaire (doublons, mauvaise adhésion, fautes de frappe mineurs, email payeur différent de l'email adhérent).
4. **Logique Métier :** - Comparaison des données avec l'historique de l'année précédente (par email, ou noms similaires en utilisant le LLM).
    - Inscription dans la feuille de l'année en cours.
    - Attribution de parcelle privative si nécessaire, selon la répartition actuelle.
5. **Communication :** Envoi automatique d'un kit de bienvenue par email (Outlook) aux nouveaux adhérents contenant le règlement, le lien pour adhérer au groupe WhatsApp et le numéro de parcelle si nécessaire.
6. **Nettoyage :** Après confirmation (Statut 200), l'email source est déplacé vers un dossier d'archives pour éviter les doublons.

## 🛠️ Stack Technique

- **Langage :** Python 3.11 (Programmation Orientée Objet)
- **Infrastructure :** AWS Lambda (Serverless), Make.com (Orchestrateur)
- **Parsing de l'email et correction des erreurs de saisie:** Mistral AI (Modèle `mistral-small-2506`)
- **Stockage :** Google Sheets API (via `gspread` et `google-auth`)
- **Communications :** Outlook API, WhatsApp API (Proof of Concept, fonctionnel en test mais non mis en production pour rester sur une application 100% gratuite)
- **DevOps :** Git/GitHub, Variables d'environnement pour la sécurité

## 📂 Structure du Projet

```text
├── core/
│   ├── parser.py           # Logique de parsing avec Mistral AI 
│   └── logic.py            # Cerveau de l'application (règles métier)
│   └── judge.py            # Diagnostic des erreurs de saisie avec Mistral AI
├── services/
│   ├── excel_manager.py    # Interface avec l'API Google Sheets
│   ├── outlook_service.py  # Gestion des envois d'emails
│   └── whatsapp_service.py # Module WhatsApp (prêt pour déploiement)
├── prompts/                # Stockage des prompts pour les LLM
├── email_templates/        # Stockage des emails pour le service d'envoi d'emails
├── tests/                  # Tests unitaires et d'intégration
├── lambda_function.py      # Point d'entrée pour AWS Lambda
├── make_com.blueprint.json # Configuration du scénario Make
├── pack.sh                 # Script de packaging pour AWS Lambda
└── requirements.txt        # Dépendances optimisées (requests privilégié)
```

## 🚀 Installation et Déploiement
### Pré-requis
- Un compte AWS (Lambda)
- Une clé API Mistral AI
- Un compte de service Google Cloud (avec accès au Google Sheets)
- Un compte Make.com
- Une adresse email Outlook

## Configuration
1. Cloner le dépôt.
2. Créer un fichier .env (non versionné) avec :
    - MISTRAL_API_KEY
    - MAKE_TRIGGER_API_KEY (pour la sécurité Lambda)
    - OUTLOOK_CLIENT_ID
    - OUTLOOK_CLIENT_SECRET
    - OUTLOOK_REFRESH_TOKEN
3. Télécharger les credentials Google au format .json et réaliser le processus nécessaire pour modifier un fichier Sheets depuis l'API Google
4. Utiliser pack.sh pour générer le .zip à uploader sur AWS Lambda.

## 🛡️ Sécurité, robustesse et performances
- Authentification : Chaque requête entre Make et Lambda est validée par un token de sécurité dans le header.
- Secrets : Chaque secret est stocké dans les variables d'environnement d'AWS Lambda.
- Gestion d'erreurs : En cas d'échec du parsing ou de l'écriture, le système ne valide pas la réception de l'email, permettant une reprise manuelle ou automatique. Les erreurs retournées sont claires et détaillées.
- Tests : Couverture de tests pour chaque service pour garantir la non-régression.
- Performance : La bibliothèque `requests` est priorisé pour les services externes afin de minimiser le nombre de bibliothèques à installer lors du lancement de la fonction Lambda.
- Environnement : Un LLM à faible nombre de paramètres activés a été choisi pour limiter l'empreinte environnementale de l'IA.