from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.visual_ui import VisualUseCase, VisualStep
from app.schemas.visual_ui import VisualUseCaseCreate, VisualUseCaseUpdate


class VisualUIService:
    
    @staticmethod
    async def get_case(db: AsyncSession, case_id: str) -> Optional[VisualUseCase]:
        stmt = select(VisualUseCase).options(selectinload(VisualUseCase.steps)).where(VisualUseCase.id == case_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_cases_by_project(db: AsyncSession, project_id: Optional[str] = None, skip: int = 0, limit: int = 20) -> List[VisualUseCase]:
        stmt = select(VisualUseCase)
        if project_id:
            stmt = stmt.where(VisualUseCase.project_id == project_id)
        
        stmt = (
            stmt.order_by(VisualUseCase.created_at.desc())
            .options(selectinload(VisualUseCase.steps))
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_case(db: AsyncSession, data: VisualUseCaseCreate) -> VisualUseCase:
        # Create base entity
        db_case = VisualUseCase(
            project_id=data.project_id,
            name=data.name,
            description=data.description,
            status=data.status,
            base_url=data.base_url
        )
        db.add(db_case)
        await db.flush()  # To gain the UUID

        # Create steps
        for step_dto in data.steps:
            db_step = VisualStep(
                case_id=db_case.id,
                step_index=step_dto.step_index,
                action=step_dto.action,
                target_description=step_dto.target_description,
                value=step_dto.value,
                screenshot_baseline=step_dto.screenshot_baseline
            )
            db.add(db_step)
        
        await db.commit()
        await db.refresh(db_case)
        return await VisualUIService.get_case(db, db_case.id)

    @staticmethod
    async def update_case(db: AsyncSession, case_id: str, data: VisualUseCaseUpdate) -> Optional[VisualUseCase]:
        # 1. Fetch current case
        stmt = select(VisualUseCase).options(selectinload(VisualUseCase.steps)).where(VisualUseCase.id == case_id)
        result = await db.execute(stmt)
        db_case = result.scalar_one_or_none()
        
        if not db_case:
            return None

        # 2. Update primitive fields
        if data.project_id is not None: db_case.project_id = data.project_id
        if data.name is not None: db_case.name = data.name
        if data.description is not None: db_case.description = data.description
        if data.status is not None: db_case.status = data.status
        if data.base_url is not None: db_case.base_url = data.base_url

        # 3. Replace steps if provided
        if data.steps is not None:
            # Delete old steps manually if cascade is not entirely synchronous
            for old_step in db_case.steps:
                await db.delete(old_step)
            db_case.steps.clear()
            await db.flush()

            # Insert new steps
            for st in data.steps:
                new_step = VisualStep(
                    case_id=db_case.id,
                    step_index=st.step_index,
                    action=st.action,
                    target_description=st.target_description,
                    value=st.value,
                    screenshot_baseline=st.screenshot_baseline
                )
                db.add(new_step)
        
        await db.commit()
        return await VisualUIService.get_case(db, case_id)

    @staticmethod
    async def delete_case(db: AsyncSession, case_id: str) -> bool:
        stmt = select(VisualUseCase).where(VisualUseCase.id == case_id)
        result = await db.execute(stmt)
        db_case = result.scalar_one_or_none()
        if not db_case:
            return False
        
        await db.delete(db_case)
        await db.commit()
        return True
