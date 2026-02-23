import api from './api';

export enum ExecutionStatus {
    PENDING = 'pending',
    RUNNING = 'running',
    PASSED = 'passed',
    FAILED = 'failed',
    ERROR = 'error',
    CANCELLED = 'cancelled'
}

export interface Execution {
    id: string;
    status: ExecutionStatus;
    total_cases?: number;
    passed_cases?: number;
    failed_cases?: number;
    duration_ms?: number;
    step_results?: any[];
}

export const executionsService = {
    getExecutionResult: async (id: string) => {
        return api.get<Execution>(`/executions/${id}/result`);
    }
};
