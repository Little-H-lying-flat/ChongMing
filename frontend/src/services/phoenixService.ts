import api from './api';

export interface TraceAction {
    type: string;
    target?: string;
    value?: string;
    description?: string;
}

export interface TraceData {
    name?: string;
    scenario_id?: string;
    actions: TraceAction[];
}

export interface CompileRequest {
    trace_id: string;
    trace_data?: TraceData;
    strategy?: 'exact' | 'optimized' | 'data_driven' | 'hybrid';
    output_format?: 'pytest' | 'unittest';
    options?: Record<string, any>;
}

export interface CompileResponse {
    script_id: string;
    file_path: string;
    code_preview: string;
    parameters_extracted: number;
    steps_generated: number;
}

export interface ScriptInfo {
    script_id: string;
    file_path: string;
    name: string;
    source_tc_id: string;
    strategy: string;
    created_at: string;
    updated_at: string;
}

export interface VersionInfo {
    version: string;
    author: string;
    date: string;
    message: string;
    changes: string;
}

export const compileTrace = async (data: CompileRequest): Promise<CompileResponse> => {
    const response = await api.post<CompileResponse>('/phoenix/compile', data);
    return response.data;
};

export const getScripts = async (skip: number = 0, limit: number = 100): Promise<ScriptInfo[]> => {
    const response = await api.get<ScriptInfo[]>(`/phoenix/scripts?skip=${skip}&limit=${limit}`);
    return response.data;
};

export const getScriptInfo = async (scriptId: string): Promise<ScriptInfo> => {
    const response = await api.get<ScriptInfo>(`/phoenix/scripts/${scriptId}`);
    return response.data;
};

export const getScriptCode = async (scriptId: string): Promise<{ code: string }> => {
    const response = await api.get<{ code: string }>(`/phoenix/scripts/${scriptId}/code`);
    return response.data;
};

export const getScriptHistory = async (scriptId: string): Promise<VersionInfo[]> => {
    const response = await api.get<VersionInfo[]>(`/phoenix/scripts/${scriptId}/history`);
    return response.data;
};

export const healScript = async (scriptId: string, brokenCode: string, errorLog: string): Promise<any> => {
    const response = await api.post<any>(`/phoenix/scripts/${scriptId}/heal`, {
        script_id: scriptId,
        healing_record_id: `HEAL_${Date.now()}`,
        error_log: errorLog,
        broken_code: brokenCode
    });
    return response.data;
};
