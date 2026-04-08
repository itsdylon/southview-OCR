from PIL import Image

from southview.ocr.bakeoff.providers import OpenAIResponsesProvider, parse_extraction_payload


def _write_png(path):
    image = Image.new("RGB", (8, 8), (255, 255, 255))
    image.save(path)


def test_parse_extraction_payload_valid_json():
    name, dod = parse_extraction_payload('{"deceased_name":"SMITH, John", "date_of_death":"2021-10-30"}')
    assert name == "SMITH, John"
    assert dod == "2021-10-30"


def test_parse_extraction_payload_embedded_json():
    raw = "```json\n{\"deceased_name\":\"SMITH, John\",\"date_of_death\":\"\"}\n```"
    name, dod = parse_extraction_payload(raw)
    assert name == "SMITH, John"
    assert dod == ""


def test_openai_provider_returns_error_row_on_api_failure(tmp_path):
    image_path = tmp_path / "card.png"
    _write_png(image_path)

    class _FailingResponses:
        def create(self, **kwargs):
            raise RuntimeError("forced openai failure")

    class _FailingClient:
        responses = _FailingResponses()

    provider = OpenAIResponsesProvider(client=_FailingClient())
    out = provider.run_model("gpt-4.1-mini", str(image_path))

    assert out.error
    assert "forced openai failure" in out.error
    assert out.deceased_name == ""
    assert out.date_of_death == ""
    assert out.latency_ms >= 0.0
