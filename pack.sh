#!/bin/bash

# --- CONFIGURATION ---
FUNCTION_NAME="auto-sub-management-tv"
ZIP_NAME="Archive.zip"

echo "🚀 Début du packaging..."

# 1. Nettoyage et préparation
rm -rf package $ZIP_NAME
mkdir package

# 2. Installation des dépendances
echo "📦 Installation des dépendances..."
pip install -r requirements.txt --target ./package --quiet

# 3. Copie du code source
echo "📂 Copie du code..."
cp -r core services email_templates prompts lambda_function.py ./package

# 4. Création de l'archive
echo "🗜️  Création de l'archive ZIP..."
cd package
zip -r ../$ZIP_NAME . > /dev/null
cd ..

echo "✅ Packaging terminé : $ZIP_NAME créé."

# 5. Upload sur AWS Lambda
# echo "☁️  Upload vers AWS (Lambda: $FUNCTION_NAME)..."
# aws lambda update-function-code \
#     --function-name $FUNCTION_NAME \
#     --zip-file fileb://$ZIP_NAME

# echo "✅ Déploiement terminé avec succès !"