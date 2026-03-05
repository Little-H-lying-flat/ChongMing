from app.models.test_case import ExecutionMode, Priority, TCStatus, TestCase as TCModel


def test_to_tcir_preserves_collection_shapes():
    tc = TCModel(
        id="TC-UNIT-0001",
        name="Model contract",
        description="shape check",
        mode=ExecutionMode.UI,
        priority=Priority.P1,
        status=TCStatus.DRAFT,
        steps=[{"action": "click", "target": "#submit"}],
        tags=["smoke"],
        dependencies=["TC-BASE-0001"],
        variables={"token": "abc"},
    )

    payload = tc.to_tcir()

    assert isinstance(payload["steps"], list)
    assert isinstance(payload["tags"], list)
    assert isinstance(payload["dependencies"], list)
    assert isinstance(payload["variables"], dict)
    assert payload["steps"][0]["action"] == "click"
