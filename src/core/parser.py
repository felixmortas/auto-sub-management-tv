import html
import re
from services.llm_client import LLMClient


class HelloAssoParser:
    """Perform business-level checks using an LLM."""

    @staticmethod
    def _clean_html(html_content: str) -> str:
        """
        Strips HTML tags, scripts, styles, and unescapes entities using standard re and html libraries.
        Preserves logical line breaks based on block-level HTML tags.
        """
        if not html_content:
            return ""

        # 1. Remove script and style tags completely along with their content
        clean_text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html_content, flags=re.DOTALL | re.IGNORECASE)

        # 2. Replace block-level elements and <br> with line breaks (\n)
        clean_text = re.sub(r'<(br|p|div|tr|li|h[1-6])[^>]*>', '\n', clean_text, flags=re.IGNORECASE)

        # 3. Strip all remaining HTML tags
        clean_text = re.sub(r'<[^>]+>', ' ', clean_text)

        # 4. Decode HTML entities (e.g. &amp; -> &)
        clean_text = html.unescape(clean_text)

        # 5. Clean up extra spaces per line while keeping line breaks intact
        lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in clean_text.splitlines()]
        
        # 6. Join lines and eliminate excessive consecutive empty lines (max 2 consecutive \n)
        return re.sub(r'\n\s*\n+', '\n', "\n".join(lines)).strip()

    @staticmethod
    def parse_email(
        email_content: str, 
        llm_client: LLMClient,
    ) -> dict:
        """Parse the email and extract member data."""
        cleaned_content = HelloAssoParser._clean_html(email_content)

        result = llm_client.call(
            system_prompt_filename="email_parser.md",
            user_message=(
                f"Contenu de l'email à parser :\n\n{cleaned_content}"
            ),
            run_name="parse_email",
        )
        adhesions_list = result.get("adhesions", [])
        for item in adhesions_list:
            if isinstance(item.get('has_plot'), str):
                item['has_plot'] = item['has_plot'].lower() == 'true'

        return adhesions_list