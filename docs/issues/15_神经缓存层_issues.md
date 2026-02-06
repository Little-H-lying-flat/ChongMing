# 神经缓存层 (Neural Cache) 开发任务

## Epic: 神经缓存层实现

**模块**: 缓存层 - 性能优化  
**优先级**: P1  
**预估工时**: 2 周  

---

## Issue #NC-001: 缓存路由器 (Cache Router)

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `cache`  
**预估**: 2d

### 描述
实现缓存路由决策器，判断请求走缓存还是走推理。

### 验收标准
- [ ] CacheRouter 类实现
- [ ] route_visual_request() 方法
- [ ] route_plan_request() 方法
- [ ] 特性开关 (Feature Flags)
- [ ] 单元测试覆盖

### 技术细节
```python
class CacheRouter:
    async def route_visual_request(screenshot, instruction, viewport) -> RouteResult
    async def route_plan_request(prd_content, api_doc, env) -> RouteResult
```

---

## Issue #NC-002: 视觉缓存 (Visual Cache)

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `cache`, `visual`  
**预估**: 3d

### 描述
基于页面感知哈希的视觉定位结果缓存。

### 验收标准
- [ ] Perceptual Hash (pHash) 实现
- [ ] 动态内容屏蔽 (时间戳/UUID/验证码)
- [ ] ROI 裁剪算法
- [ ] VisualCacheValue 数据结构
- [ ] 置信度衰减机制
- [ ] TTL 动态计算

### 技术依赖
- imagehash 库
- PIL/Pillow

---

## Issue #NC-003: 规划缓存 (Plan Cache)

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `cache`, `llm`  
**预估**: 3d

### 描述
基于意图语义相似度的规划结果缓存。

### 验收标准
- [ ] Intent Embedding 生成
- [ ] 语义相似度判断 (余弦相似度 > 0.95)
- [ ] API 文档哈希计算
- [ ] PlanCacheValue 数据结构
- [ ] 意图聚类 (Cluster)

### 技术依赖
- OpenAI Embedding API 或 本地模型
- numpy / scipy

---

## Issue #NC-004: 分层存储 (Tiered Storage)

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `cache`, `infra`  
**预估**: 2d

### 描述
实现 L1 (Memory) → L2 (Redis) → L3 (S3) 分层缓存存储。

### 验收标准
- [ ] L1 LRU 内存缓存 (1000 items)
- [ ] L2 Redis 缓存层
- [ ] L3 S3/MinIO 冷存储
- [ ] 缓存回填机制
- [ ] 归档定时任务 (Celery Beat)

### 技术依赖
- cachetools (L1)
- redis-py (L2)
- boto3 / minio (L3)

---

## Issue #NC-005: 缓存失效策略

**类型**: Feature  
**优先级**: P1  
**标签**: `backend`, `cache`  
**预估**: 2d

### 描述
实现多维度缓存失效策略。

### 验收标准
- [ ] TTL 过期
- [ ] 页面版本变化检测
- [ ] API 文档更新检测
- [ ] 置信度衰减失效 (< 0.6)
- [ ] 手动清除 API
- [ ] 低置信度不入缓存策略

---

## Issue #NC-006: 缓存 API 与监控

**类型**: Feature  
**优先级**: P1  
**标签**: `backend`, `api`, `monitoring`  
**预估**: 2d

### 描述
缓存管理 API 和 Prometheus 指标。

### 验收标准
- [ ] GET /api/v1/cache/stats
- [ ] POST /api/v1/cache/invalidate
- [ ] POST /api/v1/cache/warm
- [ ] GET /api/v1/cache/entries
- [ ] Prometheus 指标 (hits/misses/hit_rate/latency_saved)
- [ ] Grafana 仪表盘模板

---

## Checklist

- [ ] #NC-001 缓存路由器
- [ ] #NC-002 视觉缓存
- [ ] #NC-003 规划缓存
- [ ] #NC-004 分层存储
- [ ] #NC-005 失效策略
- [ ] #NC-006 API 与监控

---

## 依赖关系

```
#NC-001 (路由器)
    │
    ├──▶ #NC-002 (视觉缓存)
    │        │
    │        └──▶ #NC-004 (分层存储)
    │
    └──▶ #NC-003 (规划缓存)
             │
             └──▶ #NC-004 (分层存储)

#NC-005 (失效策略) ──▶ 依赖 #NC-002, #NC-003

#NC-006 (API/监控) ──▶ 依赖 #NC-001 ~ #NC-005
```
