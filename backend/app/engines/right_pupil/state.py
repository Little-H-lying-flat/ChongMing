from typing import TypedDict, List, Dict, Any, Optional
from app.schemas.execution import AUIIR

class AgentState(TypedDict):
    """
    Right Pupil 智能体工作流状态 (LangGraph State)
    """
    # 基础信息
    task_description: str         # 当前步骤的任务描述
    task_url: Optional[str]       # 当前步骤的目标URL (如有)
    execution_id: Optional[str]   # 执行 ID (用于发送 WebSocket Trace)
    history: List[Dict[str, Any]] # 操作历史
    
    # 循环感知与状态
    current_screenshot: Optional[str] # 当前屏幕原始截图 (Base64)
    current_dom: Optional[Dict[str, Any]] # 当前 DOM 树
    som_text: Optional[str]           # 空间锚点文本形式
    annotated_screenshot: Optional[str] # 带红框的截图 (Base64)
    id_map: Dict[str, Any]            # OmniParser 提取的 {ID: BBox} 字典
    
    # 决策输出
    action_intent: Optional[AUIIR]  # 决定的动作意图
    
    # 执行结果与评估
    action_result: Optional[Dict[str, Any]] # 执行结果 (包含截图, success)
    
    # 错误处理与重试控制
    error: Optional[str]              # 当前循环的错误/异常
    failure_type: Optional[str]       # 错误定性 (例如 PRODUCT_BUG, UI_CHANGE, NONE)
    retry_count: int                  # 当前重试次数
    max_retries: int                  # 最大允许重试次数
