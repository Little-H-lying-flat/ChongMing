from app.services.neural_design.graph import _fallback_scenarios_from_points


def test_ui_fallback_should_split_into_three_scenarios():
    points = [
        "Verify username and password input fields are visible",
        "Verify redirect to home page after valid login",
        "Verify error text appears for invalid password",
        "Verify username is prefilled when Remember Me is enabled",
    ]

    scenarios = _fallback_scenarios_from_points(points, "UI")

    assert len(scenarios) == 3
    assert scenarios[0]["name"] == "UI Happy Path Login"
    assert scenarios[1]["name"] == "UI Negative Login"
    assert scenarios[2]["name"] == "UI Remember Me"

    for scenario in scenarios:
        assert scenario["steps"], f"{scenario['name']} should have at least one step"
        assert all(step["step_type"] == "UI" for step in scenario["steps"])
        assert all("action" in step for step in scenario["steps"])
        assert scenario["priority"] == "P2"

    happy, negative, remember = scenarios
    assert any(step["action"] == "goto" for step in happy["steps"])
    assert any(step["action"] == "click" for step in negative["steps"])
    assert any("remember" in (step.get("target") or "").lower() for step in remember["steps"])
    assert all("New Browser Session" not in (step.get("target") or "") for step in remember["steps"])
    assert any("input[name='username']" == step.get("target") for step in happy["steps"])
    assert any(step.get("target") == "[data-testid='login-error']" for step in negative["steps"])


def test_api_fallback_should_keep_single_scenario():
    points = [
        "Verify unauthenticated GET /orders returns 401",
        "Verify POST /auth/login with valid credentials returns token",
    ]

    scenarios = _fallback_scenarios_from_points(points, "API")

    assert len(scenarios) == 1
    assert scenarios[0]["name"].startswith("[Fallback] API")
    assert len(scenarios[0]["steps"]) == 2
    assert all(step["step_type"] == "API" for step in scenarios[0]["steps"])
