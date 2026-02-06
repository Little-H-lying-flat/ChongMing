-- 重明 (ChongMing) 数据库初始化脚本
-- PostgreSQL 15

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ==================== 测试用例表 ====================
CREATE TABLE IF NOT EXISTS test_cases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tc_id VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(256) NOT NULL,
    mode VARCHAR(16) NOT NULL CHECK (mode IN ('UI', 'API', 'HYBRID')),
    priority VARCHAR(4) NOT NULL CHECK (priority IN ('P0', 'P1', 'P2')),
    tc_ir JSONB NOT NULL,
    status VARCHAR(16) DEFAULT 'draft',
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_test_cases_mode ON test_cases(mode);
CREATE INDEX idx_test_cases_priority ON test_cases(priority);
CREATE INDEX idx_test_cases_status ON test_cases(status);
CREATE INDEX idx_test_cases_tags ON test_cases USING GIN(tags);

-- ==================== 执行记录表 ====================
CREATE TABLE IF NOT EXISTS executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id VARCHAR(64) UNIQUE NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    total_cases INTEGER DEFAULT 0,
    passed INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    skipped INTEGER DEFAULT 0,
    config JSONB,
    environment VARCHAR(32),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_executions_status ON executions(status);
CREATE INDEX idx_executions_created ON executions(created_at DESC);

-- ==================== 执行结果表 ====================
CREATE TABLE IF NOT EXISTS execution_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id VARCHAR(64) NOT NULL REFERENCES executions(execution_id),
    tc_id VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,
    duration INTEGER,
    error_message TEXT,
    trace_log JSONB,
    screenshots TEXT[],
    recording_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_results_execution ON execution_results(execution_id);
CREATE INDEX idx_results_tc ON execution_results(tc_id);
CREATE INDEX idx_results_status ON execution_results(status);

-- ==================== 缺陷表 ====================
CREATE TABLE IF NOT EXISTS defects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    defect_id VARCHAR(64) UNIQUE NOT NULL,
    title VARCHAR(256) NOT NULL,
    error_pattern TEXT,
    root_cause JSONB,
    impact JSONB,
    fix_suggestion JSONB,
    status VARCHAR(16) DEFAULT 'open',
    severity VARCHAR(4),
    related_tc_ids TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

CREATE INDEX idx_defects_status ON defects(status);
CREATE INDEX idx_defects_severity ON defects(severity);

-- ==================== 编译脚本表 ====================
CREATE TABLE IF NOT EXISTS compiled_scripts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    script_id VARCHAR(64) UNIQUE NOT NULL,
    tc_id VARCHAR(64) NOT NULL,
    name VARCHAR(256),
    content TEXT,
    file_path VARCHAR(512),
    framework VARCHAR(32) DEFAULT 'pytest',
    parameters TEXT[],
    git_branch VARCHAR(128),
    git_commit VARCHAR(40),
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_scripts_tc ON compiled_scripts(tc_id);

-- ==================== 环境配置表 ====================
CREATE TABLE IF NOT EXISTS environments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(64) UNIQUE NOT NULL,
    type VARCHAR(16) CHECK (type IN ('dev', 'test', 'staging', 'prod')),
    urls JSONB,
    variables JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ==================== VRT 基线表 ====================
CREATE TABLE IF NOT EXISTS vrt_baselines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    page_name VARCHAR(128) NOT NULL,
    url VARCHAR(512) NOT NULL,
    browser VARCHAR(32) DEFAULT 'chromium',
    viewport JSONB,
    baseline_path VARCHAR(512),
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(page_name, browser)
);

-- ==================== VRT 报告表 ====================
CREATE TABLE IF NOT EXISTS vrt_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id VARCHAR(64) UNIQUE NOT NULL,
    baseline_id UUID REFERENCES vrt_baselines(id),
    current_path VARCHAR(512),
    diff_path VARCHAR(512),
    diff_percentage DECIMAL(5,2),
    status VARCHAR(16) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== 任务表 ====================
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id VARCHAR(64) UNIQUE NOT NULL,
    type VARCHAR(32) NOT NULL,
    priority VARCHAR(8) DEFAULT 'normal',
    status VARCHAR(16) DEFAULT 'pending',
    payload JSONB,
    result JSONB,
    error TEXT,
    celery_task_id VARCHAR(64),
    progress DECIMAL(5,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_type ON tasks(type);
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);

-- ==================== 工作流表 ====================
CREATE TABLE IF NOT EXISTS workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(64) UNIQUE NOT NULL,
    user_id VARCHAR(64),
    current_step VARCHAR(64),
    state JSONB,
    checkpoint_id VARCHAR(64),
    status VARCHAR(16) DEFAULT 'running',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_workflows_status ON workflows(status);

-- ==================== 初始数据 ====================
INSERT INTO environments (name, type, urls, variables) VALUES
('development', 'dev', '{"web": "http://localhost:3000", "api": "http://localhost:8000"}', '{}'),
('testing', 'test', '{"web": "https://test.example.com", "api": "https://test-api.example.com"}', '{}'),
('production', 'prod', '{"web": "https://example.com", "api": "https://api.example.com"}', '{}')
ON CONFLICT (name) DO NOTHING;
