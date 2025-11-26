from dataclasses import dataclass
from typing import List


@dataclass
class SeoPackage:
    title: str
    description: str
    tags: List[str]


def build_seo_english(script: str, topic: str) -> SeoPackage:
    """
    Costruisce titolo, descrizione e tag per pubblico USA.
    """
    first_sentence = script.split(".")[0].strip()
    hook = first_sentence[:80]

    title = f"{hook} | {topic}"

    description_lines = [
        script.strip(),
        "",
        "—",
        "If this was useful, hit like & subscribe for more short insights.",
        "#shorts #learn #motivation",
    ]
    description = "\n".join(description_lines)

    base_tags = ["shorts", "motivation", "learning", "usa", "english"]
    topic_tag = topic.lower().replace(" ", "")
    tags = base_tags + [topic_tag]

    return SeoPackage(title=title, description=description, tags=tags)
