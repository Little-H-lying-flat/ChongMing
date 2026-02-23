from typing import List, Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.visual_ui import VisualUseCaseCreate, VisualUseCaseUpdate, VisualUseCaseResponse
from app.services.visual_ui_service import VisualUIService

router = APIRouter()

@router.post("/cases", response_model=VisualUseCaseResponse, summary="创建视觉 UI 用例")
async def create_visual_case(
    data: VisualUseCaseCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    创建带自然语言步骤的视觉 UI 自动化测试用例
    """
    try:
        case = await VisualUIService.create_case(db, data)
        return case
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cases", response_model=List[VisualUseCaseResponse], summary="查询项目下的视觉用例")
async def list_visual_cases(
    project_id: Optional[str] = Query(None, description="项目所属ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    查询视觉 UI 用例列表（根据 project_id 过滤，如果不传则查询所有）
    """
    cases = await VisualUIService.get_cases_by_project(db, project_id, skip=skip, limit=limit)
    return cases

@router.get("/cases/{case_id}", response_model=VisualUseCaseResponse, summary="获取单个视觉用例详情")
async def get_visual_case(
    case_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取单个用例及其所有按序排列的测试步骤
    """
    case = await VisualUIService.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Visual Use Case not found")
    return case

@router.put("/cases/{case_id}", response_model=VisualUseCaseResponse, summary="更新视觉用例及步骤")
async def update_visual_case(
    case_id: str,
    data: VisualUseCaseUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    更新用例基本信息。如果提供了 `steps` 数组，将全量覆盖替换原有的步骤列表。
    """
    try:
        case = await VisualUIService.update_case(db, case_id, data)
        if not case:
            raise HTTPException(status_code=404, detail="Visual Use Case not found")
        return case
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cases/{case_id}", summary="删除视觉用例")
async def delete_visual_case(
    case_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    彻底删除该用例及关联的所有步骤
    """
    success = await VisualUIService.delete_case(db, case_id)
    if not success:
        raise HTTPException(status_code=404, detail="Visual Use Case not found")
    return {"status": "success", "message": "Case deleted"}

# === WebSocket Live Trace Manager ===

@router.post("/import-from-design", response_model=Dict[str, Any], summary="从 Neural Design 导入用例")
async def import_from_design(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """
    接收 Neural Design 生成的 Scenario 对象并转换为 Visual UI 格式
    """
    try:
        name = payload.get("name", "未命名视觉用例")
        description = payload.get("description", "")
        base_url = payload.get("base_url")
        steps_raw = payload.get("steps", [])

        # 映射自然语言动作到 VisualStepAction
        def map_action(step_desc: str) -> str:
            desc_lower = step_desc.lower()
            if any(kw in desc_lower for kw in ['open', '打开', '跳转', '访问', 'goto', 'visit', 'nav']):
                return 'GOTO'
            elif any(kw in desc_lower for kw in ['click', '点击', 'press', '按']):
                return 'CLICK'
            elif any(kw in desc_lower for kw in ['type', '输入', 'fill', '填写']):
                return 'TYPE'
            elif any(kw in desc_lower for kw in ['wait', '等待']):
                return 'WAIT'
            elif any(kw in desc_lower for kw in ['assert', '断言', '检查', '确认', '验证', 'verify', 'check']):
                return 'ASSERT'
            elif any(kw in desc_lower for kw in ['scroll', '滚动', '滑动']):
                return 'SCROLL'
            return 'CLICK' # Default fallback

        visual_steps = []
        for idx, s in enumerate(steps_raw):
            desc = s if isinstance(s, str) else s.get("description", "")
            action = map_action(desc)
            value = None
            if isinstance(s, dict) and "url" in s and s["url"]:
                value = s["url"]
            elif isinstance(s, dict) and "body" in s and s["body"]:
                value = str(s["body"])
                
            visual_steps.append({
                "step_index": idx,
                "action": action,
                "target_description": desc,
                "value": value
            })

        # 构建 VisualUseCaseCreate 数据
        from app.schemas.visual_ui import VisualUseCaseCreate
        # Provide a default project_id since it might not be passed
        project_id = payload.get("project_id", "default_project")
        
        create_data = VisualUseCaseCreate(
            project_id=project_id,
            name=name,
            description=description,
            base_url=base_url,
            steps=visual_steps
        )
        
        case = await VisualUIService.create_case(db, create_data)
        return {"status": "success", "visual_case_id": case.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Visual Import Failed: {str(e)}")

# === WebSocket Live Trace Manager ===

class VisualWSManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, execution_id: str):
        await websocket.accept()
        if execution_id not in self.active_connections:
            self.active_connections[execution_id] = []
        self.active_connections[execution_id].append(websocket)

    def disconnect(self, websocket: WebSocket, execution_id: str):
        if execution_id in self.active_connections and websocket in self.active_connections[execution_id]:
            self.active_connections[execution_id].remove(websocket)
            if not self.active_connections[execution_id]:
                del self.active_connections[execution_id]

    async def broadcast_to_execution(self, execution_id: str, message: dict):
        if execution_id in self.active_connections:
            for connection in self.active_connections[execution_id]:
                # Send the labeled image or trace log to users watching this execution
                await connection.send_json(message)

visual_ws_manager = VisualWSManager()

@router.websocket("/ws/{execution_id}")
async def visual_live_trace_ws(websocket: WebSocket, execution_id: str):
    """
    WebSocket 端点，前端用来实时接收 RightPupil Engine 执行过程中的带框截图 (Labeled Image)
    """
    await visual_ws_manager.connect(websocket, execution_id)
    try:
        while True:
            # 保持连接，等待客户端或服务端的断开
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        visual_ws_manager.disconnect(websocket, execution_id)

