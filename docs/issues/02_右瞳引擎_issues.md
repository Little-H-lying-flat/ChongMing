# 右瞳引擎 (Right Pupil Engine) 开发任务（已退役）

> Retired/Superseded：RightPupil/OmniParser 旧 UI 执行链路已移除，当前 Visual UI 执行以 Midscene Runner 和 `MidsceneAdapter` 为准。本文件仅保留历史任务背景，不代表当前实现。

## Epic: 右瞳引擎 UI 测试实现

**模块**: 执行层 - UI 测试侧  
**优先级**: P0 (核心模块)  
**预估工时**: 4 周  

---

## Issue #RP-001: OmniParser 集成

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `ai`, `visual`  
**预估**: 3d

### 描述
集成 OmniParser 视觉识别服务，实现页面元素识别。

### 验收标准
- [ ] 截图上传到 OmniParser
- [ ] 解析返回的元素坐标
- [ ] 转换为 Playwright 可用格式
- [ ] 缓存机制 (避免重复识别)

### 技术细节
```python
class OmniParserClient:
    async def detect_elements(self, screenshot: bytes) -> List[Element]
```

---

## Issue #RP-002: Visual-First 定位策略

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `playwright`  
**预估**: 4d

### 描述
实现"视觉优先、DOM 兜底"的混合定位策略。

### 验收标准
- [ ] 优先使用视觉定位
- [ ] 定位失败回退 DOM
- [ ] 多策略竞争 (first success)
- [ ] 定位超时处理
- [ ] 定位日志记录

---

## Issue #RP-003: AUI-IR 执行器

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `playwright`  
**预估**: 5d

### 描述
实现 AUI-IR 协议的执行器，将操作指令转化为 Playwright 动作。

### 验收标准
- [ ] 支持 click/fill/scroll/hover 等动作
- [ ] 支持 keyboard 操作
- [ ] 支持 file upload
- [ ] 支持 drag and drop
- [ ] 断言执行

---

## Issue #RP-004: SmartWait 智能等待

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `playwright`  
**预估**: 3d

### 描述
集成智能等待机制，自动判断页面稳定状态。

### 验收标准
- [ ] DOM 稳定检测
- [ ] 网络空闲检测
- [ ] 视觉稳定检测
- [ ] 自定义信号检测
- [ ] 多信号加权融合

---

## Issue #RP-005: 执行录屏

**类型**: Feature  
**优先级**: P1  
**标签**: `backend`, `playwright`  
**预估**: 2d

### 描述
集成执行过程录屏，记录操作轨迹。

### 验收标准
- [ ] 视频录制 (WebM)
- [ ] 关键帧截图
- [ ] 操作轨迹叠加
- [ ] 视频存储和访问

---

## Issue #RP-006: Trace Log 生成

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`  
**预估**: 2d

### 描述
生成详细的执行轨迹日志，供凤凰涅槃层编译使用。

### 验收标准
- [ ] 记录每步操作
- [ ] 记录定位策略
- [ ] 记录截图
- [ ] 记录网络请求
- [ ] JSON 格式输出

---

## Issue #RP-007: 浏览器管理

**类型**: Feature  
**优先级**: P1  
**标签**: `backend`, `playwright`  
**预估**: 2d

### 描述
实现浏览器实例池管理，支持复用和隔离。

### 验收标准
- [ ] 浏览器池管理
- [ ] Context 隔离
- [ ] 资源清理
- [ ] 多浏览器支持 (Chromium/Firefox/WebKit)

---

## Issue #RP-008: API 端点实现

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `api`  
**预估**: 2d

### 描述
实现右瞳引擎的 REST API 端点。

### 验收标准
- [ ] POST /api/v1/ui-engine/execute
- [ ] POST /api/v1/ui-engine/screenshot
- [ ] GET /api/v1/ui-engine/executions/{id}
- [ ] SSE 进度推送

---

## Issue #RP-009: Celery Worker 集成

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `celery`  
**预估**: 2d

### 描述
将 UI 执行任务封装为 Celery Task，支持异步执行。

### 验收标准
- [ ] UI 执行 Task 定义
- [ ] ui_queue 队列
- [ ] 进度回调
- [ ] 重试机制

---

## Checklist

- [ ] #RP-001 OmniParser 集成
- [ ] #RP-002 Visual-First 定位
- [ ] #RP-003 AUI-IR 执行器
- [ ] #RP-004 SmartWait 等待
- [ ] #RP-005 执行录屏
- [ ] #RP-006 Trace Log
- [ ] #RP-007 浏览器管理
- [ ] #RP-008 API 端点
- [ ] #RP-009 Celery 集成
- [ ] #RP-010 原子执行模式 🆕
- [ ] #RP-011 多级视觉聚焦 🆕

---

## Issue #RP-010: 原子执行模式 (Atomic Mode) 🆕

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `performance`, `dual-mode`  
**预估**: 3d

### 描述
实现原子执行模式，跳过 LLM 规划直接进行视觉定位执行，大幅提升回归测试速度。

### 验收标准
- [ ] 实现 AtomicExecutor 类
- [ ] 支持 atomicTap/atomicInput/atomicHover/atomicScroll/atomicSelect
- [ ] 模式路由器 ModeRouter 自动检测
- [ ] TC-IR 支持 mode: "atomic" 显式指定
- [ ] 单步延迟 < 1s (对比规划模式 3-5s)
- [ ] 与 Neural Cache 集成

### 技术细节
```python
class AtomicExecutor:
    async def execute(self, request: AtomicActionRequest) -> ActionResult:
        screenshot = await self.page.screenshot()
        coords = await self.locator.locate(screenshot, request.target)
        await self._perform_action(request.action, coords, request.value)
```

---

## Issue #RP-011: 多级视觉聚焦 (Deep Focus) 🆕

**类型**: Feature  
**优先级**: P1  
**标签**: `backend`, `visual`, `dual-mode`  
**预估**: 4d

### 描述
实现多级视觉聚焦策略，解决密集 UI (编辑器侧边栏、复杂表格) 定位精度低的问题。

### 验收标准
- [ ] Stage 1: 全局区域识别 (Qwen-VL)
- [ ] Stage 2: 区域裁剪 + OmniParser 高精度检测
- [ ] Stage 3: Qwen-VL 精确目标匹配
- [ ] 自动触发条件实现 (密度/置信度/相似元素)
- [ ] deepFocus: true 配置支持
- [ ] 密集 UI 定位精度提升至 90%+

### 技术细节
```python
class DeepFocusEngine:
    async def locate(self, screenshot: bytes, target: str) -> DeepFocusResult:
        # Stage 1: 全局区域识别
        region = await self.qwen.find_region(screenshot, target)
        # Stage 2: 区域裁剪检测
        cropped = self.crop(screenshot, region)
        elements = await self.omniparser.detect(cropped)
        # Stage 3: 精确匹配
        return await self.qwen.match_target(cropped, elements, target)
```

### 触发条件
- 元素密度 > 50 个/区域
- 首次定位置信度 < 0.7
- 匹配到多个相似元素 (如 5 个 "button")
- 用户显式指定 deepFocus: true

