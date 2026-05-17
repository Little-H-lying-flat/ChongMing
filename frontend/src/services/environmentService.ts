import { api } from './api';

export interface EnvironmentVariable {
    value: string;
    encrypted?: boolean;
    description?: string;
}

export interface Environment {
    id: string;
    name: string;
    description?: string;
    base_url: string;
    is_active: boolean;
    is_default: boolean;
    variables: Record<string, EnvironmentVariable | string>;
    headers: Record<string, string>;
    auth_type?: string;
    created_at?: string;
    updated_at?: string;
}

export interface EnvironmentCreate {
    name: string;
    base_url: string;
    description?: string;
    variables?: Record<string, EnvironmentVariable | string>;
    headers?: Record<string, string>;
    auth_type?: string;
    auth_config?: Record<string, unknown>;
    is_default?: boolean;
}

export interface EnvironmentUpdate extends Partial<EnvironmentCreate> {
    is_active?: boolean;
}

export interface HealthCheckResponse {
    environment: string;
    environment_name: string;
    timestamp: string;
    overall_status: string;
    details: Record<string, unknown>;
}

export const getEnvironments = async (active_only: boolean = false): Promise<Environment[]> => {
    const response = await api.get<Environment[]>(`/environments?active_only=${active_only}`);
    return response.data;
}

export const createEnvironment = async (data: EnvironmentCreate): Promise<Environment> => {
    const response = await api.post<Environment>('/environments', data);
    return response.data;
}

export const updateEnvironment = async (id: string, data: EnvironmentUpdate): Promise<Environment> => {
    const response = await api.put<Environment>(`/environments/${id}`, data);
    return response.data;
}

export const deleteEnvironment = async (id: string): Promise<void> => {
    await api.delete(`/environments/${id}`);
}

export const checkEnvironmentHealth = async (id: string): Promise<HealthCheckResponse> => {
    const response = await api.get<HealthCheckResponse>(`/environments/${id}/health`);
    return response.data;
}
