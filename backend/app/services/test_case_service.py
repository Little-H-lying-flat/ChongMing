"""Service layer for test case CRUD and lifecycle constraints."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import ExecutionStep
from app.models.test_case import ExecutionMode, Priority, TCStatus, TestCase


ALLOWED_TRANSITIONS: Dict[str, set[str]] = {
    "draft": {"review", "archived"},
    "review": {"draft", "active", "archived"},
    "active": {"frozen", "disabled", "archived"},
    "frozen": {"active", "disabled", "archived"},
    "disabled": {"review", "archived"},
    "archived": set(),
}


class TestCaseService:
    """Handles CRUD operations for TestCase records."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, tc_data: Dict[str, Any]) -> TestCase:
        if not tc_data.get("id"):
            tc_data["id"] = f"TC-{uuid.uuid4().hex[:8].upper()}"

        mode = tc_data.get("mode")
        if mode is not None:
            tc_data["mode"] = ExecutionMode(mode)

        priority = tc_data.get("priority")
        if priority is not None:
            tc_data["priority"] = Priority(priority)

        status = tc_data.get("status")
        if status is not None:
            tc_data["status"] = TCStatus(status)

        db_obj = TestCase(**tc_data)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def get(self, tc_id: str) -> Optional[TestCase]:
        result = await self.db.execute(select(TestCase).where(TestCase.id == tc_id))
        return result.scalars().first()

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        mode: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[TestCase]:
        query = select(TestCase)

        if status:
            query = query.where(TestCase.status == status)
        if mode:
            query = query.where(TestCase.mode == mode)
        if tag:
            # Tag filter is currently a compatibility no-op for SQLite portability.
            pass

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def count(self, status: Optional[str] = None, mode: Optional[str] = None) -> int:
        from sqlalchemy import func

        query = select(func.count(TestCase.id))
        if status:
            query = query.where(TestCase.status == status)
        if mode:
            query = query.where(TestCase.mode == mode)

        result = await self.db.execute(query)
        return result.scalar_one()

    async def update(self, tc_id: str, tc_data: Dict[str, Any]) -> Optional[TestCase]:
        existing = await self.get(tc_id)
        if existing is None:
            return None

        if "status" in tc_data and tc_data["status"] is not None:
            next_status = TCStatus(tc_data["status"])
            current_status = existing.status.value
            if next_status.value != current_status:
                allowed = ALLOWED_TRANSITIONS.get(current_status, set())
                if next_status.value not in allowed:
                    raise ValueError(
                        f"Invalid status transition: {current_status} -> {next_status.value}"
                    )
            tc_data["status"] = next_status

        if "mode" in tc_data and tc_data["mode"] is not None:
            tc_data["mode"] = ExecutionMode(tc_data["mode"])

        if "priority" in tc_data and tc_data["priority"] is not None:
            tc_data["priority"] = Priority(tc_data["priority"])

        query = (
            update(TestCase)
            .where(TestCase.id == tc_id)
            .values(**tc_data, updated_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session="fetch")
        )
        await self.db.execute(query)
        await self.db.commit()

        return await self.get(tc_id)

    async def _has_execution_reference(self, tc_id: str) -> bool:
        stmt = select(ExecutionStep.id).where(ExecutionStep.tc_id == tc_id).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def delete(self, tc_id: str) -> str:
        existing = await self.get(tc_id)
        if existing is None:
            return "not_found"

        if await self._has_execution_reference(tc_id):
            return "referenced"

        query = delete(TestCase).where(TestCase.id == tc_id)
        await self.db.execute(query)
        await self.db.commit()
        return "deleted"
