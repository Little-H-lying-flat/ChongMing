<p align="center">
  <img src="docs/assets/chongming-logo.svg" alt="重明 Logo" width="200"/>
</p>

<h1 align="center">重明 (ChongMing)</h1>

<p align="center">
  <strong>🔮 企业级 AI 原生质量工程平台 (Enterprise AI-Native Quality Platform)</strong>
</p>

<p align="center">
  <a href="#核心特性">核心特性</a> •
  <a href="#架构概览">架构概览</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#模块说明">模块说明</a> •
  <a href="#文档">文档</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-2.0.0-blue" alt="Version"/>
  <img src="https://img.shields.io/badge/license-AGPL--3.0-green" alt="License"/>
  <img src="https://img.shields.io/badge/python-3.12-yellow" alt="Python"/>
  <img src="https://img.shields.io/badge/react-18-blue" alt="React"/>
  <img src="https://img.shields.io/badge/status-stable-success" alt="Status"/>
</p>

---

## 📖 项目简介

**重明** 是下一代智能自动化测试与质量工程平台，采用独创的 **"神经-凤凰" (Neural-Phoenix)** 双脑架构。它不仅仅是一个测试工具，更是一个能"看懂"界面、"理解"业务、"自我进化"的 AI 质量专家。

区别于传统自动化工具，重明具备：
- **👁️ 视觉感知**：不依赖 DOM 定位，像人类一样通过视觉识别 UI 元素 (OmniParser)。
- **🧠 认知推理**：从需求文档 (PRD) 直接生成测试用例，理解业务逻辑。
- **🔥 自我修复**：脚本执行失败时自动分析根因并尝试自愈。
- **⚖️ 全维保障**：覆盖 UI、API、性能 (Turbo) 及视觉回归 (VRT) 测试。

> "重明"取自《山海经》神鸟，双目重瞳，能逐妖邪。寓意平台以双重洞察力（代码+视觉）消除软件缺陷。

---

## ✨ 核心特性

### 🧠 神经设计层 (Neural Design)
- **PRD → 用例**：自动解析需求文档，生成测试用例
- **AI 评审**：Critic Agent 评估用例质量
- **知识增强**：RAG 检索项目知识库

### 👁️ 双瞳引擎
- **右瞳 (UI)**：Visual-First 视觉优先定位策略
- **左瞳 (API)**：Swagger 解析 + RAG 用例增强
- **智能等待**：多信号融合页面稳定检测

### 🔥 凤凰涅槃层 (Phoenix Nirvana)
- **轨迹编译**：执行轨迹 → Pytest 脚本
- **意图注释**：LLM 添加业务语义
- **Git 集成**：自动提交到版本库

### 🚀 涡轮引擎 (Turbo)
- **极速施压**：Locust 分布式性能测试
- **实时指标**：RPS、P95/P99 延迟监控

### 🛡️ 智能运维
- **缺陷分析**：AI 根因分析 + Milvus 相似缺陷检索
- **自愈中心**：定位器自愈、数据自愈
- **VRT**：AI 驱动的视觉回归测试
### 🧠 神经设计层 (Neural Design)
- **PRD 解析**：直接上传 Markdown/PDF 需求文档，AI 自动提取测试点。
- **场景生成**：利用 `LangGraph` 编排生成的业务场景覆盖率高达 90%+。
- **Critic 评审**：内置 Critic Agent 对生成用例进行自动评审与优化。
### 👁️ 双瞳引擎 (Double Pupil)
- **右瞳 (UI / Visual-First)**：
  - 基于 **OmniParser** 的纯视觉定位，彻底解决 DOM 变动导致的脚本脆性问题。
  - **Smart Wait**：结合视觉相似度 (SSIM) 与网络状态的双因子智能等待。
- **左瞳 (API / Spec-Driven)**：
  - 自动解析 Swagger/OpenAPI 生成测试脚本。
  - **RAG 增强**：结合向量知识库理解 API 间的依赖关系。

### 🔥 凤凰涅槃层 (Phoenix Nirvana)
- **轨迹编译**：将自然语言/手动操作轨迹实时编译为标准 Pytest 脚本。
- **Git 集成**：生成的脚本自动提交至 Git 仓库，纳入版本管理。
- **视觉回归 (VRT)**：AI 驱动的视觉对比，自动剔除广告/时间等动态噪点。

### 🚀 涡轮引擎 (Turbo)
- **分布式压测**：基于 Locust 的大规模并发测试，支持动态扩容。
- **数据合成**：AI 根据 Schema 自动生成海量高保真测试数据。

### 🛡️ 智能运维 (Smart Ops)
- **缺陷分析**：利用 Milvus 向量检索相似历史缺陷，AI 自动判定根因。
- **模型治理**：动态路由 AI 模型 (如切换 Qwen-Max/GPT-4)，即时调整 Prompt。
---

## 🏗️ 架构概览

### 三态生命周期

```
         ┌─────────────────────────────────────────────────────────────┐
         │                    三态生命周期 (Three-State Lifecycle)      │
         │                                                             │
         │    ┌──────────┐       ┌──────────┐       ┌──────────┐      │
         │    │   液态   │  ──▶  │   固态   │  ──▶  │   气态   │      │
         │    │ (Liquid) │       │ (Solid)  │       │ (Gaseous)│      │
         │    │          │       │          │       │          │      │
         │    │ AI 探索  │       │ 脚本固化 │       │ 持续执行 │      │
         │    └──────────┘       └──────────┘       └──────────┘      │
         └─────────────────────────────────────────────────────────────┘
```

### 核心分层架构 (Core Layered Architecture)

本项目采用严格的 **API -> Services -> Engines** 分层架构，确保职责单一和代码解耦。

```mermaid
graph TD
    User[用户/PRD] --> Neural[🧠 神经设计层]
    Neural --> |生成| Cases[测试用例]
    
    subgraph Execution [双瞳执行引擎]
       Cases --> RightPupil[👁️ 右瞳 (UI/视觉)]
        Cas es --> LeftPupil[👁️ 左瞳 (API)]
        RightPupil --> |视觉感知| Omni[OmniParser]
        LeftPupil --> |语义理解| RAG[RAG 知识库]
    end
    
    subgraph Nirvana [🔥 凤凰涅槃层]
        RightPupil --> Trace[执行轨迹]
        Trace --> Compiler[编译器]
        Compiler --> Script[Pytest 脚本]
        Script --> Git[Git 仓库]
    end
    
    subgraph Ops [🛡️ 智能运维]
        Script --> Result[执行结果]
        Result --> Defect[缺陷分析 (Milvus)]
        Result --> VRT[视觉回归]
    end
    
    subgraph Turbo [🚀 涡轮引擎]
        Cases --> LoadTest[性能压测 (Locust)]
    end
```

---

## 🚀 快速开始

### 前置要求
- Docker & Docker Compose (v2.0+)
- Nvidia GPU (推荐，用于 OmniParser 视觉模型)
- CPU 模式亦可运行 (速度较慢)

### 1. 启动服务
重明提供了一键部署脚本，包含数据库、向量库及所有微服务。

```bash
# 克隆仓库
git clone https://github.com/Little-H-lying-flat/ChongMing.git
cd ChongMing

# 配置环境变量 (必须设置 API Key)
cp deploy/.env.example deploy/.env
# 编辑 deploy/.env 填入 QWEN_API_KEY 等信息

# 启动 (生产模式)
docker-compose -f deploy/docker-compose.yml up -d

Navigate to frontend: cd frontend
Start dev server: npm run dev
Open browser: http://localhost:3000/executions     
```
前端启动命令 请在 d:\project\ChongMing\frontend 目录下运行：

powershell
npm run dev
后端启动命令 请在 d:\project\ChongMing\backend 目录下运行（确保已激活虚拟环境）：

powershell
cd backend
# 如果未激活虚拟环境:
.\.venv-py312\Scripts\Activate.ps1
# 启动服务:
python -m uvicorn app.main:app --reload
python -m uvicorn app.main:app --reload --loop asyncio

python run.py --reload
### 2. 访问服务

| 服务 | 地址 | 默认账号 |
|------|------|----------|
| **前端控制台** | http://localhost:3000 | admin / admin |
| **API 文档** | http://localhost:8000/docs | - |
| **Flower (监控)** | http://localhost:5555 | admin / admin123 |
| **Grafana** | http://localhost:3001 | admin / admin123 |
| **MinIO (S3)** | http://localhost:9001 | minioadmin / minioadmin |

---

## 🔧 技术栈

### Backend (Python 3.12)
- **Framework**: FastAPI, Celery, LangChain, LangGraph
- **Test Engines**: Playwright (UI), Locust (Load), Pytest
- **AI/ML**: OmniParser (Vision), Qwen-VL (Multimodal), OpenAI SDK
- **Database**: PostgreSQL (Data), Redis (Cache), ChromaDB & Milvus (Vector)

### Frontend (React 18)
- **Core**: Next.js, TypeScript, React Query
- **UI**: TailwindCSS, ShadcnUI, Monaco Editor
- **Viz**: Recharts, React-Flow

---

## � 模块目录

```bash
backend/
├── app/
│   ├── api/             # RESTful 接口
│   ├── core/            # 核心配置 (AI Client, DB)
│   ├── engines/         # 执行引擎
│   │   ├── right_pupil/ # UI 视觉引擎
│   │   ├── left_pupil/  # API 引擎
│   │   └── turbo/       # 性能引擎
│   ├── services/        # 业务逻辑
│   │   ├── neural_design/ # PRD 解析
│   │   ├── phoenix/       # 脚本编译与 Git
│   │   └── smart_ops/     # 缺陷分析与治理
│   └── tasks/           # Celery 异步任务
├── tests/               # 单元与集成测试
└── pyproject.toml       # 依赖管理
```

---

## 📄 开源协议

MIT License @ ChongMing Team

---
<p align="center">Made with ❤️ for Quality Engineering</p>
