import api from './api';

export interface ApiRequestSpec {
    method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
    url: string;
    headers: Record<string, string>;
    body?: unknown;
    query_params: Record<string, string>;
    timeout_ms: number;
}

export interface ApiAssertion {
    status_code?: number;
    json_assertions: Record<string, unknown>;
    contains?: string;
    not_contains?: string;
    expression?: string;
}

export interface ApiStep {
    id: string;
    name: string;
    request: ApiRequestSpec;
    extraction: Record<string, string>;
    assertion?: ApiAssertion;
}

export interface ApiTestCase {
    id?: string;
    name: string;
    description: string;
    mode: "API";
    priority: "P0" | "P1" | "P2" | "P3";
    status: "active" | "draft" | "disabled";
    steps: ApiStep[];
    tags: string[];
    created_at?: string;
    updated_at?: string;
}

// Responses from Left Pupil Execution
export interface ExecutionStepResult {
    step_id: string;
    status: "passed" | "failed" | "error";
    status_code: number;
    duration_ms: number;
    extracted_values: Record<string, unknown>;
    assertion_passed: boolean;
    assertion_details?: Record<string, unknown>;
    error?: string;
    request_details?: {
        method: string;
        url: string;
        headers: Record<string, string>;
        body?: unknown;
    };
    response_details?: {
        headers: Record<string, string>;
        body: unknown;
    };
}

export interface ChainExecutionResult {
    success: boolean;
    total_steps: number;
    passed_steps: number;
    failed_steps: number;
    results: ExecutionStepResult[];
    final_context: Record<string, unknown>;
}

export const apiAutoService = {
    // 1. 获取用例类
    getCases: (params?: { page?: number, pageSize?: number }) => {
        const queryParams = new URLSearchParams();
        queryParams.append('page', (params?.page || 1).toString());
        queryParams.append('page_size', (params?.pageSize || 100).toString());
        queryParams.append('mode', 'API');
        return api.get<{ items: ApiTestCase[], total: number, page: number, page_size: number }>(`/test-cases?${queryParams.toString()}`);
    },

    getCaseById: (id: string) => {
        return api.get<ApiTestCase>(`/test-cases/${id}`);
    },

    createCase: (data: Partial<ApiTestCase>) => {
        return api.post<ApiTestCase>('/test-cases', {
            ...data,
            mode: "API",
            priority: data.priority || "P1"
        });
    },

    updateCase: (id: string, data: Partial<ApiTestCase>) => {
        return api.put<ApiTestCase>(`/test-cases/${id}`, data);
    },

    deleteCase: (id: string) => {
        return api.delete(`/test-cases/${id}`);
    },

    // 2. 执行引擎类
    runApiChain: (
        steps: ApiStep[],
        baseUrl: string,
        context: Record<string, unknown> = {},
        defaultHeaders: Record<string, string> = {},
        envId?: string
    ) => {
        return api.post<ChainExecutionResult>('/left-pupil/execute-chain', {
            base_url: baseUrl,
            steps,
            context,
            default_headers: defaultHeaders,
            stop_on_failure: true,
            env_id: envId
        });
    }
};
