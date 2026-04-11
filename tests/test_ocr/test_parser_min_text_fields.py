from southview.ocr.parser_min import parse_fields_from_text


def test_parse_fields_from_text_prefers_labeled_death_and_burial_dates():
    raw_text = """AARON, Benjamin L.
ESTATE
c/o Mrs. Helen Reaves - Mother
Owner
Ph# (404) 784-2878
5566 Marbut Road Lithonia, GA.
Relation:
Date of death
dob 6/27/1966
December 8, 2004
Date of burial
December 14, 2004
Description:
LOT# 316 Range B Grave# 2
Section 4 Block 5 Northside
Sex M
Age
38
Type of Grave
SVC Vault
Grave Fee $675.00
Undertaker Haugabrooks
"""

    fields = parse_fields_from_text(raw_text)

    assert fields["owner_name"]["value"] == "AARON, Benjamin L."
    assert fields["owner_address"]["value"] == "5566 Marbut Road Lithonia, GA."
    assert fields["care_of"]["value"] == "Mrs. Helen Reaves - Mother"
    assert fields["phone"]["value"] == "(404) 784-2878"
    assert fields["date_of_death"]["value"] == "2004-12-08"
    assert fields["date_of_burial"]["value"] == "2004-12-14"
    assert fields["description"]["value"] == "LOT# 316 Range B Grave# 2 Section 4 Block 5 Northside"
    assert fields["sex"]["value"] == "M"
    assert fields["age"]["value"] == "38"
    assert fields["type_of_grave"]["value"] == "SVC Vault"
    assert fields["grave_fee"]["value"] == "675.00"
    assert fields["undertaker"]["value"] == "Haugabrooks"


def test_parse_fields_from_text_does_not_promote_burial_date_to_death_date():
    raw_text = """ANNON, Benjamin L. 5556 Marhot Road. Lithonia, Ga.
ESTATE
Date of Death December 8, 2004
Date of Burial December 14, 2004
Phone (440) 786-8578
Helen Reserve - Mother
deb 6/27/1956
"""

    fields = parse_fields_from_text(raw_text)

    assert fields["date_of_death"]["value"] == "2004-12-08"
    assert fields["date_of_burial"]["value"] == "2004-12-14"


def test_parse_fields_from_text_uses_unlabeled_dates_before_dob_for_death_and_burial():
    raw_text = """AARON, Benjamin L.
ESTATE
c/o Mrs. Helen Reeves - Mother
5566 Marshbrook Rd.
Litchfield, GA.
Ph # (404) 784-2578
December 8, 2004
December 14, 2004
dob 12/27/1966
"""

    fields = parse_fields_from_text(raw_text)

    assert fields["date_of_death"]["value"] == "2004-12-08"
    assert fields["date_of_burial"]["value"] == "2004-12-14"


def test_parse_fields_from_text_does_not_duplicate_identical_unlabeled_dates_into_both_fields():
    raw_text = """AARON, Benjamin L.
ESTATE
c/o Mrs. Helen Reeves - Mother
5566 Marshbrook Rd.
Litchfield, GA.
Ph # (404) 784-2578
December 14, 2004
December 14, 2004
dob 12/27/1966
"""

    fields = parse_fields_from_text(raw_text)

    assert fields["date_of_death"]["value"] is None
    assert fields["date_of_burial"]["value"] == "2004-12-14"


def test_parse_fields_from_text_reads_multiline_description_and_svc():
    raw_text = """ADAMS, James
Owner
Relation:
Date of death
Date of burial
3-20-41
Description: Lot #64- Range G- Grave 9- Section 2- Block 2 SS
Sex M. Age 54 Type of Grave
Undertaker
Cox
Board of Health No.
8047A
Grave Fee
125.00
SVC No.
8047
"""

    fields = parse_fields_from_text(raw_text)

    assert fields["owner_name"]["value"] == "ADAMS, James"
    assert fields["date_of_burial"]["value"] == "1941-03-20"
    assert fields["description"]["value"] == "Lot #64- Range G- Grave 9- Section 2- Block 2 SS"
    assert fields["sex"]["value"] == "M"
    assert fields["age"]["value"] == "54"
    assert fields["undertaker"]["value"] == "Cox"
    assert fields["board_of_health_no"]["value"] == "8047A"
    assert fields["grave_fee"]["value"] == "125.00"
    assert fields["svc_no"]["value"] == "8047"


def test_parse_fields_from_text_reads_unlabeled_svc_no_after_grave_fee():
    raw_text = """AARON, Benjamin L.
Type of Grave SVC Vault
Grave Fee $75.00
49,711
PACKAGE
"""

    fields = parse_fields_from_text(raw_text)

    assert fields["svc_no"]["value"] == "49,711"


def test_parse_fields_from_text_builds_location_description_without_description_label():
    raw_text = """AARON, Benjamin L.
Date of burial: December 14, 2004
Date of death: December 8, 2004
Direction:
Section 4 Block 5 Northside
LOT #316 Range B Grave # 2
"""

    fields = parse_fields_from_text(raw_text)

    assert fields["description"]["value"] == "Section 4 Block 5 Northside LOT #316 Range B Grave # 2"


def test_parse_fields_from_text_uses_1900s_for_two_digit_years():
    raw_text = """ADAMS, James
Date of burial
3-20-41
"""

    fields = parse_fields_from_text(raw_text)

    assert fields["date_of_burial"]["value"] == "1941-03-20"


def test_parse_fields_from_text_does_not_fill_death_from_combined_death_burial_line():
    raw_text = """ADAMS, James
Date of death Date of burial 3-20-41
"""

    fields = parse_fields_from_text(raw_text)

    assert fields["date_of_death"]["value"] is None
    assert fields["date_of_burial"]["value"] == "1941-03-20"


def test_parse_fields_from_text_reads_undertaker_from_previous_line_when_label_follows():
    raw_text = """ADAMS, James
Board of Health No.
Cox
Undertaker
Grave Fee
Sex
M
"""

    fields = parse_fields_from_text(raw_text)

    assert fields["undertaker"]["value"] == "Cox"


def test_parse_fields_from_text_does_not_use_grave_fee_as_undertaker_or_description_as_grave_type():
    raw_text = """ADAMS, James
Board of Health No.
Cox
Undertaker
Grave Fee
Sex
M
Age
54
Type of Grave
Description: Lot #64- Range G- Grave 9- Section 2- Block 2 SS
"""

    fields = parse_fields_from_text(raw_text)

    assert fields["undertaker"]["value"] == "Cox"
    assert fields["type_of_grave"]["value"] is None
