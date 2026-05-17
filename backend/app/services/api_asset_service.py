"""Service layer for API endpoint assets."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_asset import ApiAsset
from app.services.api_case_ir_converter import normalize_api_step_v2
from app.services.left_pupil.swagger_parser import ApiEndpoint, SwaggerParser


class ApiAssetConflictError(ValueError):
    pass


class ApiAssetService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: Dict[str, Any]) -> ApiAsset:
        payload = self._prepare_payload(data, source_type=data.get("source_type") or "manual")
        if not payload.get("id"):
            payload["id"] = self._new_id()

        if await self._get_by_asset_key(payload["asset_key"]):
            raise ApiAssetConflictError(f"API asset already exists: {payload['asset_key']}")

        db_obj = ApiAsset(**payload)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def get(self, asset_id: str) -> Optional[ApiAsset]:
        result = await self.db.execute(select(ApiAsset).where(ApiAsset.id == asset_id))
        return result.scalars().first()

    async def update(self, asset_id: str, data: Dict[str, Any]) -> Optional[ApiAsset]:
        existing = await self.get(asset_id)
        if existing is None:
            return None

        merged = self._asset_to_payload(existing)
        merged.update({key: value for key, value in data.items() if value is not None})
        payload = self._prepare_payload(merged, source_type=merged.get("source_type") or existing.source_type)
        payload.pop("id", None)
        payload.pop("created_at", None)
        payload["updated_at"] = datetime.now(timezone.utc)

        duplicate = await self._get_by_asset_key(payload["asset_key"])
        if duplicate and duplicate.id != asset_id:
            raise ApiAssetConflictError(f"API asset already exists: {payload['asset_key']}")

        for key, value in payload.items():
            setattr(existing, key, value)

        await self.db.commit()
        await self.db.refresh(existing)
        return existing

    async def delete(self, asset_id: str) -> bool:
        existing = await self.get(asset_id)
        if existing is None:
            return False
        await self.db.delete(existing)
        await self.db.commit()
        return True

    def to_api_ir_step(self, asset: ApiAsset) -> Dict[str, Any]:
        body = self._sample_body_from_request_body(asset.request_body)
        query_params = self._sample_params(asset.parameters, "query")
        path_params = self._sample_params(asset.parameters, "path")
        headers = self._sample_params(asset.parameters, "header")
        status_code = self._default_status_code(asset.responses)

        step = {
            "id": f"STEP_{asset.id}",
            "name": asset.summary or asset.name or f"{asset.method} {asset.path}",
            "description": asset.description or asset.summary or asset.name or f"{asset.method} {asset.path}",
            "step_type": "API",
            "request": {
                "method": asset.method,
                "url": asset.path,
                "path": asset.path,
                "headers": headers,
                "query_params": query_params,
                "path_params": path_params,
                "body": body,
                "timeout_ms": 30000,
                "content_type": (asset.request_body or {}).get("content_type", "application/json") if asset.request_body else "application/json",
            },
            "assertion": {
                "status_code": status_code,
                "json_assertions": {},
            },
            "extraction": {},
            "metadata": {
                "source_type": "api_asset",
                "source_id": asset.id,
                "asset_key": asset.asset_key,
                "source_name": asset.source_name,
                "operation_id": asset.operation_id,
                "tags": asset.tags or [],
            },
        }
        if asset.base_url:
            step["request"]["base_url"] = asset.base_url
        return normalize_api_step_v2(step, "API")

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        method: Optional[str] = None,
        tag: Optional[str] = None,
        source_name: Optional[str] = None,
        deprecated: Optional[bool] = None,
    ) -> List[ApiAsset]:
        query = self._apply_filters(
            select(ApiAsset),
            keyword=keyword,
            method=method,
            tag=tag,
            source_name=source_name,
            deprecated=deprecated,
        )
        query = query.order_by(ApiAsset.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def count(
        self,
        keyword: Optional[str] = None,
        method: Optional[str] = None,
        tag: Optional[str] = None,
        source_name: Optional[str] = None,
        deprecated: Optional[bool] = None,
    ) -> int:
        query = self._apply_filters(
            select(func.count(ApiAsset.id)),
            keyword=keyword,
            method=method,
            tag=tag,
            source_name=source_name,
            deprecated=deprecated,
        )
        result = await self.db.execute(query)
        return result.scalar_one()

    async def import_from_spec(
        self,
        content: Dict[str, Any],
        source_name: Optional[str] = None,
        source_url: Optional[str] = None,
        source_type: str = "openapi_content",
    ) -> Dict[str, Any]:
        parser = SwaggerParser()
        endpoints = parser.parse(content)
        return await self._persist_parsed_endpoints(
            parser=parser,
            endpoints=endpoints,
            source_name=source_name,
            source_url=source_url,
            source_type=source_type,
        )

    async def import_from_url(
        self,
        url: str,
        source_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        parser = SwaggerParser()
        endpoints = await asyncio.to_thread(parser.parse_url, url)
        return await self._persist_parsed_endpoints(
            parser=parser,
            endpoints=endpoints,
            source_name=source_name,
            source_url=url,
            source_type="openapi_url",
        )

    async def _persist_parsed_endpoints(
        self,
        parser: SwaggerParser,
        endpoints: Sequence[ApiEndpoint],
        source_name: Optional[str],
        source_url: Optional[str],
        source_type: str,
    ) -> Dict[str, Any]:
        info = parser.get_info()
        resolved_source_name = source_name or info.get("title") or "default"
        created_count = 0
        updated_count = 0
        skipped_count = 0
        asset_ids: list[str] = []

        for endpoint in endpoints:
            try:
                payload = self._endpoint_to_payload(
                    endpoint,
                    source_name=resolved_source_name,
                    source_type=source_type,
                    source_url=source_url,
                    spec_title=info.get("title") or None,
                    spec_version=info.get("version") or None,
                    base_url=info.get("base_path") or None,
                )
                existing = await self._get_by_asset_key(payload["asset_key"])
                if existing:
                    await self.update(existing.id, payload)
                    updated_count += 1
                    asset_ids.append(existing.id)
                else:
                    created = await self.create(payload)
                    created_count += 1
                    asset_ids.append(created.id)
            except Exception:
                skipped_count += 1

        return {
            "success": True,
            "source_name": resolved_source_name,
            "spec_title": info.get("title") or "",
            "spec_version": info.get("version") or "",
            "parsed_count": len(endpoints),
            "created_count": created_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "asset_ids": asset_ids,
        }

    def _apply_filters(self, query, **filters):
        keyword = filters.get("keyword")
        method = filters.get("method")
        tag = filters.get("tag")
        source_name = filters.get("source_name")
        deprecated = filters.get("deprecated")

        if keyword:
            pattern = f"%{keyword.strip().lower()}%"
            query = query.where(
                or_(
                    func.lower(ApiAsset.method).like(pattern),
                    func.lower(ApiAsset.path).like(pattern),
                    func.lower(ApiAsset.name).like(pattern),
                    func.lower(ApiAsset.summary).like(pattern),
                    func.lower(ApiAsset.description).like(pattern),
                    func.lower(ApiAsset.operation_id).like(pattern),
                    func.lower(ApiAsset.search_text).like(pattern),
                )
            )
        if method:
            query = query.where(ApiAsset.method == method.upper())
        if tag:
            query = query.where(func.lower(ApiAsset.search_text).like(f"%{tag.strip().lower()}%"))
        if source_name:
            query = query.where(ApiAsset.source_name == source_name)
        if deprecated is not None:
            query = query.where(ApiAsset.deprecated == deprecated)
        return query

    async def _get_by_asset_key(self, asset_key: str) -> Optional[ApiAsset]:
        result = await self.db.execute(select(ApiAsset).where(ApiAsset.asset_key == asset_key))
        return result.scalars().first()

    def _prepare_payload(self, data: Dict[str, Any], source_type: str) -> Dict[str, Any]:
        payload = dict(data)
        method = str(payload.get("method") or "GET").upper()
        path = str(payload.get("path") or "/")
        source_name = str(payload.get("source_name") or "default")
        summary = payload.get("summary") or ""
        operation_id = payload.get("operation_id") or None
        name = payload.get("name") or summary or operation_id or f"{method} {path}"

        payload.update(
            {
                "method": method,
                "path": path,
                "source_name": source_name,
                "source_type": source_type,
                "asset_key": self._asset_key(source_name, method, path),
                "name": name,
                "summary": summary or None,
                "description": payload.get("description") or None,
                "operation_id": operation_id,
                "tags": payload.get("tags") or [],
                "parameters": payload.get("parameters") or [],
                "request_body": payload.get("request_body"),
                "responses": payload.get("responses") or {},
                "security": payload.get("security") or [],
                "deprecated": bool(payload.get("deprecated", False)),
            }
        )
        payload["search_text"] = self._build_search_text(payload)
        return payload

    def _endpoint_to_payload(
        self,
        endpoint: ApiEndpoint,
        source_name: str,
        source_type: str,
        source_url: Optional[str],
        spec_title: Optional[str],
        spec_version: Optional[str],
        base_url: Optional[str],
    ) -> Dict[str, Any]:
        return self._prepare_payload(
            {
                "source_name": source_name,
                "source_type": source_type,
                "source_url": source_url,
                "spec_title": spec_title,
                "spec_version": spec_version,
                "base_url": base_url,
                "method": endpoint.method,
                "path": endpoint.path,
                "summary": endpoint.summary,
                "description": endpoint.description,
                "operation_id": endpoint.operation_id,
                "tags": endpoint.tags,
                "parameters": [asdict(param) for param in endpoint.parameters],
                "request_body": asdict(endpoint.request_body) if endpoint.request_body else None,
                "responses": {
                    status_code: asdict(response)
                    for status_code, response in endpoint.responses.items()
                },
                "security": endpoint.security,
                "deprecated": endpoint.deprecated,
            },
            source_type=source_type,
        )

    def _asset_to_payload(self, asset: ApiAsset) -> Dict[str, Any]:
        return {
            "id": asset.id,
            "source_name": asset.source_name,
            "source_type": asset.source_type,
            "source_url": asset.source_url,
            "spec_title": asset.spec_title,
            "spec_version": asset.spec_version,
            "base_url": asset.base_url,
            "name": asset.name,
            "method": asset.method,
            "path": asset.path,
            "summary": asset.summary,
            "description": asset.description,
            "operation_id": asset.operation_id,
            "tags": asset.tags,
            "parameters": asset.parameters,
            "request_body": asset.request_body,
            "responses": asset.responses,
            "security": asset.security,
            "deprecated": asset.deprecated,
        }

    def _sample_params(self, parameters: Any, location: str) -> Dict[str, Any]:
        result: dict[str, Any] = {}
        for parameter in parameters or []:
            if not isinstance(parameter, dict) or parameter.get("location") != location:
                continue
            name = parameter.get("name")
            if not name:
                continue
            result[str(name)] = self._sample_value(parameter.get("schema_type"), parameter.get("default"), parameter.get("enum"))
        return result

    def _sample_body_from_request_body(self, request_body: Any) -> Any:
        if not isinstance(request_body, dict):
            return None
        schema = request_body.get("schema") or {}
        if not isinstance(schema, dict):
            return None
        return self._sample_from_schema(schema)

    def _sample_from_schema(self, schema: Dict[str, Any]) -> Any:
        if "example" in schema:
            return schema["example"]
        if "default" in schema:
            return schema["default"]
        if "enum" in schema and schema["enum"]:
            return schema["enum"][0]

        schema_type = schema.get("type")
        if schema_type == "object" or "properties" in schema:
            return {
                key: self._sample_from_schema(value)
                for key, value in (schema.get("properties") or {}).items()
                if isinstance(value, dict)
            }
        if schema_type == "array":
            items = schema.get("items") if isinstance(schema.get("items"), dict) else {}
            return [self._sample_from_schema(items)]
        return self._sample_value(schema_type)

    def _sample_value(self, schema_type: Any, default: Any = None, enum: Any = None) -> Any:
        if default is not None:
            return default
        if enum:
            return enum[0]
        if schema_type in {"integer", "number"}:
            return 0
        if schema_type == "boolean":
            return False
        if schema_type == "array":
            return []
        if schema_type == "object":
            return {}
        return ""

    def _default_status_code(self, responses: Any) -> int:
        if not isinstance(responses, dict) or not responses:
            return 200
        for status_code in ("200", "201", "204"):
            if status_code in responses:
                return int(status_code)
        for status_code in responses:
            if str(status_code).isdigit():
                return int(status_code)
        return 200

    def _build_search_text(self, payload: Dict[str, Any]) -> str:
        parts: list[str] = [
            payload.get("method") or "",
            payload.get("path") or "",
            payload.get("name") or "",
            payload.get("summary") or "",
            payload.get("description") or "",
            payload.get("operation_id") or "",
            " ".join(payload.get("tags") or []),
        ]
        for parameter in payload.get("parameters") or []:
            if isinstance(parameter, dict):
                parts.extend(
                    [
                        str(parameter.get("name") or ""),
                        str(parameter.get("location") or ""),
                        str(parameter.get("description") or ""),
                    ]
                )
        if payload.get("request_body"):
            parts.append(str(payload["request_body"]))
        if payload.get("responses"):
            parts.append(str(payload["responses"]))
        return "\n".join(part for part in parts if part).lower()

    def _asset_key(self, source_name: str, method: str, path: str) -> str:
        return f"{source_name}:{method.upper()} {path}"

    def _new_id(self) -> str:
        return f"API-ASSET-{uuid.uuid4().hex[:8].upper()}"
