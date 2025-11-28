from src.fhir_mappings import WITHINGS_TO_FHIR

def test_weight_mapping():
    assert 1 in WITHINGS_TO_FHIR
    assert WITHINGS_TO_FHIR[1]["loinc"] == "29463-7"
    assert WITHINGS_TO_FHIR[1]["display"] == "Body weight"
    assert WITHINGS_TO_FHIR[1]["unit"] == "kg"

def test_blood_pressure_mappings():
    assert 10 in WITHINGS_TO_FHIR  # Systolic
    assert 11 in WITHINGS_TO_FHIR  # Diastolic
    assert WITHINGS_TO_FHIR[10]["loinc"] == "8480-6"
    assert WITHINGS_TO_FHIR[11]["loinc"] == "8462-4"

def test_all_mappings_have_required_fields():
    for mtype, fhir in WITHINGS_TO_FHIR.items():
        assert "loinc" in fhir, f"Missing loinc for type {mtype}"
        assert "display" in fhir, f"Missing display for type {mtype}"
        assert "unit" in fhir, f"Missing unit for type {mtype}"