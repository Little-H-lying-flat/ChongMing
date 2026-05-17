from __future__ import annotations

import pytest

from app.services.api_asset_service import ApiAssetConflictError, ApiAssetService


def _openapi_spec(summary: str = "List users") -> dict:
    return {
        "openapi": "3.0.0",
        "info": {"title": "User API", "version": "1.0.0"},
        "servers": [{"url": "https://api.example.test"}],
        "paths": {
            "/users": {
                "get": {
                    "summary": summary,
                    "operationId": "listUsers",
                    "tags": ["users"],
                    "parameters": [
                        {
                            "name": "page",
                            "in": "query",
                            "required": False,
                            "description": "Page number",
                            "schema": {"type": "integer", "default": 1},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "array"}
                                }
                            },
                        }
                    },
                },
                "post": {
                    "summary": "Create user",
                    "operationId": "createUser",
                    "tags": ["users"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        },
                    },
                    "responses": {"201": {"description": "Created"}},
                },
            }
        },
    }


@pytest.mark.asyncio
async def test_manual_asset_crud_and_method_normalization(db_session) -> None:
    service = ApiAssetService(db_session)

    created = await service.create(
        {
            "method": "get",
            "path": "/health",
            "summary": "Health check",
            "tags": ["system"],
            "source_name": "manual-suite",
        }
    )

    assert created.id.startswith("API-ASSET-")
    assert created.method == "GET"
    assert created.asset_key == "manual-suite:GET /health"
    assert "health" in created.search_text

    fetched = await service.get(created.id)
    assert fetched is not None
    assert fetched.path == "/health"

    updated = await service.update(created.id, {"summary": "Updated health", "tags": ["system", "smoke"]})
    assert updated is not None
    assert updated.summary == "Updated health"
    assert "smoke" in updated.search_text

    assert await service.delete(created.id) is True
    assert await service.get(created.id) is None


@pytest.mark.asyncio
async def test_duplicate_asset_key_raises_conflict(db_session) -> None:
    service = ApiAssetService(db_session)
    payload = {"method": "GET", "path": "/users", "source_name": "manual-suite"}

    await service.create(payload)

    with pytest.raises(ApiAssetConflictError):
        await service.create(payload)


@pytest.mark.asyncio
async def test_import_openapi_creates_assets_and_reimport_updates(db_session) -> None:
    service = ApiAssetService(db_session)

    first = await service.import_from_spec(_openapi_spec(), source_name="user-service")
    assert first["parsed_count"] == 2
    assert first["created_count"] == 2
    assert first["updated_count"] == 0
    assert first["skipped_count"] == 0

    second = await service.import_from_spec(_openapi_spec(summary="List all users"), source_name="user-service")
    assert second["parsed_count"] == 2
    assert second["created_count"] == 0
    assert second["updated_count"] == 2

    items = await service.list(keyword="all users", method="GET")
    assert len(items) == 1
    assert items[0].summary == "List all users"
    assert items[0].spec_title == "User API"
    assert items[0].spec_version == "1.0.0"
    assert items[0].base_url == "https://api.example.test"


@pytest.mark.asyncio
async def test_search_text_includes_tags_and_parameter_names(db_session) -> None:
    service = ApiAssetService(db_session)
    await service.import_from_spec(_openapi_spec(), source_name="user-service")

    by_tag = await service.list(tag="users")
    assert len(by_tag) == 2

    by_param = await service.list(keyword="page")
    assert len(by_param) == 1
    assert by_param[0].path == "/users"
    assert by_param[0].method == "GET"


@pytest.mark.asyncio
async def test_asset_can_generate_api_case_ir_v2_step(db_session) -> None:
    service = ApiAssetService(db_session)
    await service.import_from_spec(_openapi_spec(), source_name="user-service")
    assets = await service.list(keyword="create user", method="POST")

    step = service.to_api_ir_step(assets[0])

    assert step["protocol"] == "API-IR"
    assert step["version"] == "2.0"
    assert step["step_type"] == "API"
    assert step["request"]["method"] == "POST"
    assert step["request"]["url"] == "/users"
    assert step["request"]["path"] == "/users"
    assert step["request"]["body"] == {}
    assert step["assertion"]["status_code"] == 201
    assert step["expected_status_code"] == 201
    assert step["metadata"]["source_type"] == "api_asset"
    assert step["metadata"]["source_id"] == assets[0].id
