from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime, timezone

from app.models.test_case import TestCase, TCStatus, ExecutionMode, Priority

class TestCaseService:
    """
    Test Case Service
    
    Handles CRUD operations for Test Cases.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def create(self, tc_data: Dict[str, Any]) -> TestCase:
        """Create a new test case"""
        # Generate ID if not present
        if not tc_data.get("id"):
            tc_data["id"] = f"TC-{uuid.uuid4().hex[:8].upper()}"
            
        db_obj = TestCase(**tc_data)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def get(self, tc_id: str) -> Optional[TestCase]:
        """Get a test case by ID"""
        result = await self.db.execute(select(TestCase).where(TestCase.id == tc_id))
        return result.scalars().first()

    async def list(
        self, 
        page: int = 1, 
        page_size: int = 20,
        status: Optional[str] = None,
        mode: Optional[str] = None,
        tag: Optional[str] = None
    ) -> List[TestCase]:
        """List test cases with filters"""
        query = select(TestCase)
        
        if status:
            query = query.where(TestCase.status == status)
        if mode:
            query = query.where(TestCase.mode == mode)
        if tag:
            # Simple tag filtering (JSON array contains)
            # Note: Specific JSON operators depend on DB dialect (Postgres uses @>)
            # For compat, strictly we might need deeper implementation.
            # Assuming simple check or skipping for MVP if complex.
            pass

        # Pagination
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def count(self, status: Optional[str] = None, mode: Optional[str] = None) -> int:
        """Count total test cases"""
        from sqlalchemy import func
        query = select(func.count(TestCase.id))
        if status:
            query = query.where(TestCase.status == status)
        if mode:
            query = query.where(TestCase.mode == mode)
            
        result = await self.db.execute(query)
        return result.scalar_one()

    async def update(self, tc_id: str, tc_data: Dict[str, Any]) -> Optional[TestCase]:
        """Update a test case"""
        # Filter out None values to allow partial updates if needed, 
        # but typically Pydantic models handle default/optional.
        # Here we assume tc_data contains fields to update.
        
        query = (
            update(TestCase)
            .where(TestCase.id == tc_id)
            .values(**tc_data, updated_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session="fetch")
        )
        await self.db.execute(query)
        await self.db.commit()
        
        return await self.get(tc_id)

    async def delete(self, tc_id: str) -> bool:
        """Delete a test case"""
        query = delete(TestCase).where(TestCase.id == tc_id)
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount > 0
