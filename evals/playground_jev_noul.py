import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.services.jev_client import JevClient
from src.services.langsmith_tracer import LangSmithTracer

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
# Initialization
# ---------------------------------------------------------------------------

tracer = LangSmithTracer(api_key=os.environ.get("LANGSMITH_API_KEY"), project=os.environ.get("LANGSMITH_PROJECT"))

client = JevClient(model=AI_GATEWAY_MODEL, url=AI_GATEWAY_URL, api_key=AI_GATEWAY_API_KEY, tracer=tracer)

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
    inputs = example["inputs"]
    state = {
        "Nom complet à comparer": inputs["full_name"],
        "Noms des membres de l'année précédente": inputs["members_names"],
    }

    print("\n" + "=" * 80)
    print("REQUEST")
    print("=" * 80)

    for key, value in state.items():
        print(f"{key:<20}: {value}")

    answer = client.ask_boolean("names_similarity_judge_noul.md", state)

    if answer is not None:
        print("\n" + "=" * 80)
        print("ANSWER")
        print("=" * 80)

        print(f"Result : {answer}")


if __name__ == "__main__":
    main()
