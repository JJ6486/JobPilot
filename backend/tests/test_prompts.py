import re

from app.llm.prompts import load_prompt, load_sections


def test_latest_versions_load() -> None:
    assert load_prompt("analyze").version == "analyze_v5"
    assert load_prompt("tailor").version.startswith("tailor_v")
    _, rules = load_sections("tailor_rules")
    assert set(rules) == {"software_ict", "teaching"}


def test_all_placeholders_get_filled() -> None:
    values = {
        "TODAY": "x",
        "TRUTH_BANK": "x",
        "JD_TEXT": "x",
        "ANALYSIS": "x",
        "ROLE_FAMILY": "x",
        "RESUME_RULES": "x",
        "TONE": "x",
        "AVOID_PHRASES": "x",
    }
    for name in ("analyze", "tailor"):
        system, user = load_prompt(name).render(**values)
        left = set(re.findall(r"\{\{(\w+)\}\}", system + user)) - {"NAME"}  # NAME is filled locally
        assert left == set(), (name, left)
