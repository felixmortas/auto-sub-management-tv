import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

AI_GATEWAY_API_KEY = os.environ["AI_GATEWAY_API_KEY"]
AI_GATEWAY_URL = "https://ai-gateway.vercel.sh/v1/evaluate"
AI_GATEWAY_MODEL = "typesafe-ai/jev"

DATASET_PATH = Path(
    "evals/datasets/names_similarity_judge.jsonl"
)


# ---------------------------------------------------------------------------
# Jev question
# ---------------------------------------------------------------------------

INSTRUCTIONS = """# Rôle
Tu es un expert en réconciliation de données et en analyse d'identité.
Ton rôle est de déterminer si un nom donné correspond à un individu présent dans une liste de membres, même en cas de légères variations orthographiques ou d'inversion entre le nom et le prénom.

# Tâche
Compare le "Nom complet à comparer" avec la liste des "Noms des membres de l'année précédente" et indique si tu trouves une correspondance.

# Règles de correspondance
- Identité stricte : Le nom est exactement le même.
- Inversion : Le prénom et le nom sont inversés (ex: "Jean Dupont" vs "Dupont Jean").
- Similitude forte : Il existe une faute de frappe mineure, mais l'identité ne fait aucun doute (ex: "Marie Marange" vs "Maria Maranje").
- Composés : Gestion des traits d'union, des accents ou des noms composés (ex: "Marie-Pierre" vs "Marie Pierre").
"""


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

def load_example(example_id: str) -> dict:
    """Load one example from the JSONL dataset by its id."""

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset introuvable : {DATASET_PATH}"
        )

    with DATASET_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            example = json.loads(line)

            if str(example.get("id")) == str(example_id):
                return example

    raise ValueError(
        f"Aucun exemple avec l'id={example_id!r} "
        f"dans {DATASET_PATH}"
    )


# ---------------------------------------------------------------------------
# Build Jev request
# ---------------------------------------------------------------------------

def build_request(example: dict) -> dict:
    inputs = example["inputs"]

    state = {
        "Nom complet à comparer": inputs["full_name"],
        "Noms des membres de l'année précédente": inputs["members_names"],
    }

    return {
        "model": AI_GATEWAY_MODEL,
        "state": state,
        "questions": {
            "is_name_similar": {
                "type": "boolean",
                "instructions": INSTRUCTIONS,
            }
        },
    }


# ---------------------------------------------------------------------------
# Call Jev
# ---------------------------------------------------------------------------

def call_jev(payload: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {AI_GATEWAY_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        AI_GATEWAY_URL,
        headers=headers,
        json=payload,
        timeout=120,
    )

    # En cas d'erreur, afficher le corps retourné par Vercel.
    # C'est beaucoup plus utile qu'un simple "400 Bad Request".
    if not response.ok:
        print("\n" + "=" * 80)
        print("JEV ERROR")
        print("=" * 80)
        print(f"HTTP status: {response.status_code}")
        print(response.text)

        response.raise_for_status()

    return response.json()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Usage: python -m evals.playground_jev <dataset_example_id>"
        )
        print(
            "Exemple: python -m evals.playground_jev 1"
        )
        sys.exit(1)

    example_id = sys.argv[1]

    example = load_example(example_id)
    payload = build_request(example)

    print("=" * 80)
    print(f"Dataset example: {example_id}")
    print("=" * 80)

    print("\nExpected:")
    print(
        json.dumps(
            example.get("expected"),
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\n" + "=" * 80)
    print("REQUEST")
    print("=" * 80)

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\n" + "=" * 80)
    print("CALLING JEV")
    print("=" * 80)

    print(f"URL   : {AI_GATEWAY_URL}")
    print(f"Model : {AI_GATEWAY_MODEL}")

    result = call_jev(payload)

    print("\n" + "=" * 80)
    print("JEV RESPONSE")
    print("=" * 80)

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    # Affichage pratique de la réponse de la question.
    answer = (
        result
        .get("answers", {})
        .get("is_name_similar")
    )

    if answer is not None:
        print("\n" + "=" * 80)
        print("ANSWER")
        print("=" * 80)

        print(
            json.dumps(
                answer,
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
