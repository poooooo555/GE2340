#that file just for tidy up the ai return json
import json
import re


def extract_json(text: str) -> dict:
    text = (text or "").strip()

    # Remove ```json ... ``` fences if the model added them

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: grab the outermost { ... } block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise