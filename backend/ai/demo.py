"""Supply deterministic sample proposals for development without a model service."""

import json
from typing import Any


class DemoTextModel:
    """Demonstrate the review flow with clearly identified sample tasks."""

    provider = "demo"

    def generate(self, prompt: str, response_schema: dict[str, Any]) -> str:
        """Return sample tasks within the requested schema's item-count boundaries."""
        limits = response_schema["properties"]["tasks"]
        count = min(max(limits.get("minItems", 1), 5), limits.get("maxItems", 50))
        examples = [
            "Określić cel i oczekiwany efekt projektu",
            "Zebrać materiały i najważniejsze wymagania",
            "Przygotować pierwszą wersję rozwiązania",
            "Sprawdzić rezultat i wprowadzić poprawki",
            "Podsumować postępy i zaplanować kolejne kroki",
        ]
        tasks = [
            {
                "title": examples[index % len(examples)]
                + (f" — etap {index + 1}" if count > 5 else "")
            }
            for index in range(count)
        ]
        return json.dumps({"tasks": tasks}, ensure_ascii=False)
