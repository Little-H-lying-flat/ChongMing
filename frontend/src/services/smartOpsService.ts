import { api } from './api';

export interface AIModel {
    model_id: string;
    provider: string;
    capability: string;
    description: string;
    cost_per_1k_tokens: number;
}

export interface AIModuleConfig {
    module: string;
    model_id: string;
    provider: string;
    temperature: number | null;
    max_tokens: number | null;
    is_custom: boolean;
}

export interface UpdateAIConfigRequest {
    module: string;
    model_id: string;
    temperature?: number | null;
    max_tokens?: number | null;
}

export interface ProviderConfigSchema {
    provider: string;
    api_key: string;
    base_url?: string;
}

export const getAvailableModels = async (): Promise<AIModel[]> => {
    const response = await api.get<AIModel[]>('/smart-ops/models');
    return response.data;
};

export const getModuleConfigs = async (): Promise<AIModuleConfig[]> => {
    const response = await api.get<AIModuleConfig[]>('/smart-ops/config');
    return response.data;
};

export const updateModuleConfig = async (data: UpdateAIConfigRequest): Promise<AIModuleConfig> => {
    const response = await api.post<AIModuleConfig>('/smart-ops/config', data);
    return response.data;
};

export const updateProviderKey = async (data: ProviderConfigSchema): Promise<any> => {
    const response = await api.post<any>('/smart-ops/provider', data);
    return response.data;
};

export interface TokenUsageMetric {
    date: string;
    cost: number;
    [model_id: string]: number | string; // For dynamic model token keys
}

export const getTokenUsageMetrics = async (days: number = 7): Promise<TokenUsageMetric[]> => {
    const response = await api.get<TokenUsageMetric[]>(`/smart-ops/metrics/tokens?days=${days}`);
    return response.data;
};

// --- Defect Root Cause Analysis Interfaces ---

export interface DefectRecord {
    id: number;
    execution_step_id: number | null;
    error_msg: string;
    root_cause: string;
    suggested_fix: string;
    created_at: string;
}

export interface DefectAnalysisRequest {
    error_msg: string;
    context?: string;
}

export interface DefectAnalysisResponse {
    analysis: {
        root_cause: string;
        suggested_fix: string;
    };
    similar_defects: Partial<DefectRecord>[];
}

// --- Defect Analysis API calls ---

export const analyzeDefect = async (data: DefectAnalysisRequest): Promise<DefectAnalysisResponse> => {
    const response = await api.post<DefectAnalysisResponse>('/smart-ops/analyze-defect', data);
    return response.data;
};

export const getHistoricalDefects = async (): Promise<DefectRecord[]> => {
    const response = await api.get<DefectRecord[]>('/smart-ops/defects');
    return response.data;
};

export const saveDefectAnalysis = async (data: Partial<DefectRecord>): Promise<DefectRecord> => {
    const response = await api.post<DefectRecord>('/smart-ops/defects', data);
    return response.data;
};
