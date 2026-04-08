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
