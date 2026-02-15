from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict
from pydantic import Field

from app.schemas.api_ir import APIIR

class TurboMode(str, Enum):
    """运行模式"""
    LOCAL = "local"
    DISTRIBUTED = "distributed"
    K8S = "k8s"

@dataclass
class TurboRunConfig:
    """涡轮引擎运行配置"""
    target_host: str = Field(..., description="目标主机地址", example="https://api.example.com")
    test_id: Optional[str] = Field(None, description="测试任务 ID (可选，自动生成)", example="test_123456")
    users: int = Field(100, description="并发虚拟用户数 (VU)", example=200)
    spawn_rate: float = Field(10.0, description="每秒启动用户数 (Ramp-up)", example=20.0)
    run_time: str = Field("10m", description="运行时长 (如 10m, 1h)", example="5m")
    mode: TurboMode = Field(TurboMode.LOCAL, description="运行模式")
    worker_count: int = Field(1, description="分布式节点数量", example=3)
    api_ir_chain: List[APIIR] = Field(default_factory=list, description="测试链路定义")
    data_count: int = Field(1000, description="合成数据量 (行)", example=5000)
    
@dataclass
class TurboTestStats:
    """压测实时统计"""
    test_id: str = Field(..., description="测试 ID")
    state: str = Field(..., description="当前状态 (running, stopped)", example="running")
    users: int = Field(..., description="当前活跃用户数")
    total_requests: int = Field(..., description="总请求数")
    total_failures: int = Field(..., description="总失败数")
    current_rps: float = Field(..., description="当前 RPS (req/s)")
    fail_ratio: float = Field(..., description="失败率 (0.0 - 1.0)")
    avg_response_time: float = Field(..., description="平均响应时间 (ms)")
    p95_response_time: float = Field(..., description="P95 响应时间 (ms)")
