from app.main import create_app


def test_smart_ops_provider_route_registered_once() -> None:
    app = create_app()
    matches = [
        route
        for route in app.router.routes
        if getattr(route, "path", "") == "/api/v1/smart-ops/provider"
        and "POST" in getattr(route, "methods", set())
    ]
    assert len(matches) == 1
