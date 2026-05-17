from __future__ import annotations

import pytest


def _openapi_spec() -> dict:
    return {
        "openapi": "3.0.0",
        "info": {"title": "Catalog API", "version": "2026.1"},
        "servers": [{"url": "https://catalog.example.test"}],
        "paths": {
            "/products": {
                "get": {
                    "summary": "List products",
                    "operationId": "listProducts",
                    "tags": ["catalog"],
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "description": "Search keyword",
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }


@pytest.mark.asyncio
async def test_import_openapi_list_search_and_detail_flow(client) -> None:
    imported = await client.post(
        "/api/v1/api-assets/import-openapi",
        json={"content": _openapi_spec(), "source_name": "catalog-service"},
    )
    assert imported.status_code == 200
    import_body = imported.json()
    assert import_body["success"] is True
    assert import_body["source_name"] == "catalog-service"
    assert import_body["spec_title"] == "Catalog API"
    assert import_body["parsed_count"] == 1
    assert import_body["created_count"] == 1
    assert import_body["updated_count"] == 0

    listed = await client.get("/api/v1/api-assets?keyword=products&method=GET&page=1&page_size=20")
    assert listed.status_code == 200
    list_body = listed.json()
    assert list_body["total"] == 1
    assert list_body["page"] == 1
    assert list_body["page_size"] == 20
    asset = list_body["items"][0]
    assert asset["method"] == "GET"
    assert asset["path"] == "/products"
    assert asset["tags"] == ["catalog"]
    assert asset["parameters"][0]["name"] == "q"

    detail = await client.get(f"/api/v1/api-assets/{asset['id']}")
    assert detail.status_code == 200
    assert detail.json()["operation_id"] == "listProducts"

    ir_step = await client.get(f"/api/v1/api-assets/{asset['id']}/api-ir-step")
    assert ir_step.status_code == 200
    step = ir_step.json()["step"]
    assert step["protocol"] == "API-IR"
    assert step["version"] == "2.0"
    assert step["request"]["method"] == "GET"
    assert step["request"]["url"] == "/products"
    assert step["request"]["query_params"] == {"q": ""}
    assert step["assertion"]["status_code"] == 200
    assert step["metadata"]["source_type"] == "api_asset"
    assert step["metadata"]["source_id"] == asset["id"]

    reimported = await client.post(
        "/api/v1/api-assets/import-openapi",
        json={"content": _openapi_spec(), "source_name": "catalog-service"},
    )
    assert reimported.status_code == 200
    assert reimported.json()["created_count"] == 0
    assert reimported.json()["updated_count"] == 1

    after_reimport = await client.get("/api/v1/api-assets?source_name=catalog-service")
    assert after_reimport.status_code == 200
    assert after_reimport.json()["total"] == 1


@pytest.mark.asyncio
async def test_manual_asset_create_duplicate_update_and_delete_flow(client) -> None:
    payload = {
        "method": "post",
        "path": "/orders",
        "summary": "Create order",
        "tags": ["orders"],
        "source_name": "manual-suite",
        "request_body": {"content_type": "application/json", "schema": {"type": "object"}},
        "responses": {"201": {"description": "Created"}},
    }

    created = await client.post("/api/v1/api-assets", json=payload)
    assert created.status_code == 201
    created_body = created.json()
    assert created_body["method"] == "POST"
    assert created_body["asset_key"] == "manual-suite:POST /orders"

    duplicate = await client.post("/api/v1/api-assets", json=payload)
    assert duplicate.status_code == 409

    updated = await client.put(
        f"/api/v1/api-assets/{created_body['id']}",
        json={"summary": "Create order v2", "tags": ["orders", "checkout"]},
    )
    assert updated.status_code == 200
    assert updated.json()["summary"] == "Create order v2"
    assert updated.json()["tags"] == ["orders", "checkout"]

    searched = await client.get("/api/v1/api-assets?tag=checkout")
    assert searched.status_code == 200
    assert searched.json()["total"] == 1

    deleted = await client.delete(f"/api/v1/api-assets/{created_body['id']}")
    assert deleted.status_code == 204

    missing = await client.get(f"/api/v1/api-assets/{created_body['id']}")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_import_openapi_requires_exactly_one_source(client) -> None:
    missing = await client.post("/api/v1/api-assets/import-openapi", json={})
    assert missing.status_code == 400

    both = await client.post(
        "/api/v1/api-assets/import-openapi",
        json={"url": "https://example.test/openapi.json", "content": _openapi_spec()},
    )
    assert both.status_code == 400
