from services.llm_client import LLMClient


class Judge:
    """Perform business-level checks using an LLM."""

    @staticmethod
    def check_names(
        full_name: str,
        members_names: list[str],
        llm_client: LLMClient,
    ) -> dict:
        """Check whether a full name matches existing member names."""
        result = llm_client.call(
            system_prompt_filename="names_similarity_judge.md",
            user_message=(
                f"Nom complet à comparer : {full_name}\n\n"
                f"Noms des membres de l'année précédente :\n{members_names}"
            ),
            run_name="check_names",
        )

        # Sécurité : On s'assure que les booléens sont corrects pour Excel
        # (Certains LLM peuvent renvoyer des strings "true" au lieu de booleens)
        if isinstance(result.get('similarity_found'), str):
            result['similarity_found'] = result['similarity_found'].lower() == 'true'

        return result