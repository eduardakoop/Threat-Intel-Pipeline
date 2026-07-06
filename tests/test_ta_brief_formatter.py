from ta_pipeline.pipeline.ta_brief_formatter import format_ta_brief


def test_format_ta_brief_renders_expected_sections():
    payload = {
        "title": "Example Threat",
        "subtitle": "Short risk summary.",
        "introduction": "Threat intro.",
        "threat_landscape_targets": "Finance organizations appear affected.",
        "ttps": ["Phishing for initial access", "PowerShell execution"],
        "iocs": ["example.com", "198.51.100.10"],
        "defensive_strategies_best_practices": ["Block the domain", "Hunt for PowerShell abuse"],
        "references": ["Article One - https://example.com/article"],
    }

    rendered = format_ta_brief(payload)

    assert "1. Title\nExample Threat" in rendered
    assert "2. Subtitle\nShort risk summary." in rendered
    assert "5. Tactics, Techniques, and Procedures (TTPs)\n- Phishing for initial access" in rendered
    assert "6. Indicators of Compromise (IOCs)\n- example.com" in rendered
    assert "8. References\n- Article One - https://example.com/article" in rendered


def test_format_ta_brief_uses_not_reported_fallbacks():
    rendered = format_ta_brief({})

    assert "1. Title\nNot reported" in rendered
    assert "3. Introduction\nNot reported." in rendered
    assert "6. Indicators of Compromise (IOCs)\nNot reported." in rendered
    assert "8. References\nNot reported." in rendered
