from parser import parse_brd_text


def test_parse_brd_text_extracts_sections():
    text = """
    Problem:
    Manual triage slows response.

    Objectives:
    - Reduce response time
    - Auto-route tickets

    Functional Requirements:
    - Ingest email
    - Classify severity
    """
    result = parse_brd_text(text)
    assert result["schema"] == "brd_sections_v1"
    assert result["sections"]["problem"]
    assert len(result["sections"]["objectives"]) > 0
