from services.llm_client import LLMClient


class HelloAssoParser:
    """Perform business-level checks using an LLM."""

    @staticmethod
    def parse_email(
        email_content: str, 
        llm_client: LLMClient,
    ) -> dict:
        """Parse the email and extract member data."""
        result = llm_client.call(
            system_prompt_filename="email_parser.md",
            user_message=(
                f"Contenu de l'email à parser :\n\n{email_content}"
            ),
            run_name="parse_email",
        )
        adhesions_list = result.get("adhesions", [])
        for item in adhesions_list:
            if isinstance(item.get('has_plot'), str):
                item['has_plot'] = item['has_plot'].lower() == 'true'

        return adhesions_list