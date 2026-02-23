import api from './api';

export interface ApiRequestSpec {
    method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
    url: string;
    headers: Record<string, string>;
    body?: any;
    query_params: Record<string, string>;
    timeout_ms: number;
}

export interface ApiAssertion {
    status_code?: number;
    json_assertions: Record<string, any>;
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
    extracted_values: Record<string, any>;
    assertion_passed: boolean;
    assertion_details?: any;
    error?: string;
    request_details?: {
        method: string;
        url: string;
        headers: Record<string, string>;
        body?: any;
    };
    response_details?: {
        headers: Record<string, string>;
        body: any;
    };
}

export interface ChainExecutionResult {
    success: boolean;
    total_steps: number;
    passed_steps: number;
    failed_steps: number;
    results: ExecutionStepResult[];
    final_context: Record<string, any>;
}

export const apiAutoService = {
    // 1. 获取用例类
    getCases: (params?: { page?: number, pageSize?: number }) => {
        const queryParams = new URLSearchParams();
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.pageSize) queryParams.append('pageSize', params.pageSize.toString());
        queryParams.append('mode', 'API');
        return api.get<{ items: ApiTestCase[], total: number }>(`/test-cases?${queryParams.toString()}`);
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
        context: Record<string, any> = {},
        defaultHeaders: Record<string, string> = {}
    ) => {
        return api.post<ChainExecutionResult>('/left-pupil/execute-chain', {
            base_url: baseUrl,
            steps,
            context,
            default_headers: defaultHeaders,
            stop_on_failure: true
        });
    }
};
