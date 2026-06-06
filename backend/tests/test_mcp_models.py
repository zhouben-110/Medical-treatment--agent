def test_disease_table_shape():
    from medical_kb_mcp.models import Disease, Base
    t = Base.metadata.tables["diseases"]
    cols = set(t.columns.keys())
    assert {"id", "name", "symptoms", "description",
            "treatment", "when_to_see_doctor", "severity"} <= cols
    idx_names = {i.name for i in t.indexes}
    assert "ix_diseases_symptoms_gin" in idx_names
