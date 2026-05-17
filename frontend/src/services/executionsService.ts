import api from './api';

export enum ExecutionStatus {
    PENDING = 'pending',
    RUNNING = 'running',
    PASSED = 'passed',
    FAILED = 'failed',
    ERROR = 'error',
    CANCELLED = 'cancelled'
}

export interface ExecutionStepResult {
    step_index?: number;
    success: boolean;
    description?: string;
    details?: Record<string, unknown>;
    duration_ms: number;
    error?: string;
    screenshot?: string;
}

export interface ExecutionCaseResult {
    tc_id: string;
    status: ExecutionStatus;
    duration_ms: number;
    steps: ExecutionStepResult[];
    variable_trace?: Record<string, unknown>[];
    error?: string | null;
}

export interface Execution {
    id?: string;
    execution_id?: string;
    status: ExecutionStatus;
    total_cases?: number;
    passed_cases?: number;
    failed_cases?: number;
    duration_ms?: number;
    duration_seconds?: number;
    summary?: {
        total: number;
        passed: number;
        failed: number;
        skipped: number;
    };
    cases?: ExecutionCaseResult[];
    step_results?: Record<string, unknown>[];
    report_url?: string | null;
}

export const executionsService = {
    getExecutionResult: async (id: string) => {
        return api.get<Execution>(`/executions/${id}/result`);
    }
};
