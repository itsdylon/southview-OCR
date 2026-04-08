from southview.ocr.bakeoff.scoring import build_prediction_record, summarize_predictions
from southview.ocr.bakeoff.types import AdjudicationRecord, ManifestRecord, ProviderResult


def test_build_prediction_record_normalized_exact_match():
    card = ManifestRecord(
        card_id="c1",
        image_path="/tmp/card.png",
        difficulty_bucket="hard",
        deceased_name="SMITH, John",
        date_of_death="2021-10-30",
    )
    result = ProviderResult(
        deceased_name="  smith,   JOHN ",
        date_of_death="10/30/2021",
        raw_text='{"deceased_name":"smith, JOHN", "date_of_death":"10/30/2021"}',
    )

    row = build_prediction_record(card, model_id="gpt-4.1-mini", result=result)

    assert row.name_match is True
    assert row.dod_match is True
    assert row.exact_match is True


def test_build_prediction_record_blank_date_matches_blank_gt():
    card = ManifestRecord(
        card_id="c2",
        image_path="/tmp/card2.png",
        difficulty_bucket="easy",
        deceased_name="DOE, Jane",
        date_of_death="",
    )
    result = ProviderResult(
        deceased_name="DOE, Jane",
        date_of_death="",
        raw_text='{"deceased_name":"DOE, Jane", "date_of_death":""}',
    )

    row = build_prediction_record(card, model_id="gpt-4o", result=result)

    assert row.name_match is True
    assert row.dod_match is True
    assert row.exact_match is True


def test_adjudication_override_takes_precedence():
    card = ManifestRecord(
        card_id="c3",
        image_path="/tmp/card3.png",
        difficulty_bucket="hard",
        deceased_name="PARKS, Carlies Jr",
        date_of_death="1997-12-07",
    )

    prediction = build_prediction_record(
        card,
        model_id="gemini-2.0-flash",
        result=ProviderResult(
            deceased_name="PARKS, Carlies Sr",
            date_of_death="",
            raw_text='{"deceased_name":"PARKS, Carlies Sr", "date_of_death":""}',
        ),
    )

    summary_without = summarize_predictions([prediction])
    model_without = summary_without["models"][0]
    assert model_without["exact_accuracy"] == 0.0

    adj = AdjudicationRecord(
        card_id="c3",
        model_id="gemini-2.0-flash",
        human_name_correct=True,
        human_dod_correct=True,
        adjudication_notes="Human reviewer accepted handwriting interpretation.",
    )
    summary_with = summarize_predictions([prediction], adjudications=[adj])
    model_with = summary_with["models"][0]

    assert model_with["exact_accuracy"] == 1.0
    assert summary_with["ranking"][0]["model_id"] == "gemini-2.0-flash"


def test_summarize_predictions_includes_roundtrip_timer_metrics():
    cards = [
        ManifestRecord(
            card_id="c10",
            image_path="/tmp/card10.png",
            difficulty_bucket="easy",
            deceased_name="SMITH, John",
            date_of_death="2021-10-30",
        ),
        ManifestRecord(
            card_id="c11",
            image_path="/tmp/card11.png",
            difficulty_bucket="easy",
            deceased_name="DOE, Jane",
            date_of_death="1940-01-05",
        ),
        ManifestRecord(
            card_id="c12",
            image_path="/tmp/card12.png",
            difficulty_bucket="hard",
            deceased_name="PARKS, Carl",
            date_of_death="1999-12-07",
        ),
    ]
    latencies = [100.0, 200.0, 300.0]
    predictions = []
    for card, latency in zip(cards, latencies):
        predictions.append(
            build_prediction_record(
                card,
                model_id="gpt-4.1-mini",
                result=ProviderResult(
                    deceased_name=card.deceased_name,
                    date_of_death=card.date_of_death,
                    raw_text="{}",
                    latency_ms=latency,
                ),
            )
        )

    summary = summarize_predictions(predictions)
    model = summary["models"][0]

    assert model["avg_roundtrip_ms"] == 200.0
    assert model["min_roundtrip_ms"] == 100.0
    assert model["max_roundtrip_ms"] == 300.0
    assert model["total_roundtrip_ms"] == 600.0
    assert model["p50_roundtrip_ms"] == 200.0
    assert model["p95_roundtrip_ms"] == 290.0
    assert summary["ranking"][0]["avg_roundtrip_ms"] == 200.0
    assert summary["ranking"][0]["p95_roundtrip_ms"] == 290.0
