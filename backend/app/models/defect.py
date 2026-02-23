from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class DefectRecord(Base):
    """
    缺陷追踪记录 (Defect Record)
    记录自动化执行期间发生失败的执行步骤、产生的错误信息、以及 AI 根因分析结果。
    """
    __tablename__ = "defect_records"

    id = Column(Integer, primary_key=True, index=True)
    
    # 关联到产生错误的那次具体执行步骤（可选，如果是由全局外部错误引起则为空）
    execution_step_id = Column(Integer, ForeignKey("execution_steps.id", ondelete="SET NULL"), nullable=True)
    
    # 原始报错信息
    error_msg = Column(Text, nullable=False)
    
    # 智能诊断结果: 根因分析
    root_cause = Column(Text, nullable=False)
    
    # 智能诊断结果: 修复建议
    suggested_fix = Column(Text, nullable=False)
    
    # 辅助快照 (Base64 or MinIO path) - 暂时预留
    snapshot_url = Column(String(512), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    execution_step = relationship("ExecutionStep", backref="defects")
