import api from './api';
import type { ApiStep } from './apiAutoService';

export interface ApiAssetParameter {
    name: string;
    location: string;
    required?: boolean;
    description?: string;
    schema_type?: string;
    default?: unknown;
    enum?: unknown[];
}

export interface ApiAssetResponseSpec {
    status_code?: string | number;
    description?: string;
    schema?: Record<string, unknown>;
}

export interface ApiAsset {
    id: string;
    asset_key: string;
    source_name: string;
    source_type: string;
    source_url?: string | null;
    spec_title?: string | null;
    spec_version?: string | null;
    base_url?: string | null;
    name: string;
    method: string;
    path: string;
    summary?: string | null;
    description?: string | null;
    operation_id?: string | null;
    tags: string[];
    parameters: ApiAssetParameter[];
    request_body?: Record<string, unknown> | null;
    responses: Record<string, ApiAssetResponseSpec>;
    security: Record<string, unknown>[];
    deprecated: boolean;
    created_at?: string;
    updated_at?: string;
}

export interface ApiAssetListParams {
    page?: number;
    pageSize?: number;
    keyword?: string;
    method?: string;
    tag?: string;
    sourceName?: string;
    deprecated?: boolean;
}

export interface ApiAssetListResponse {
    items: ApiAsset[];
    total: number;
    page: number;
    page_size: number;
}

export interface ApiIRStepResponse {
    step: ApiStep;
}

export const apiAssetService = {
    listAssets: (params?: ApiAssetListParams) => {
        const queryParams = new URLSearchParams();
        queryParams.append('page', (params?.page || 1).toString());
        queryParams.append('page_size', (params?.pageSize || 20).toString());

        if (params?.keyword?.trim()) queryParams.append('keyword', params.keyword.trim());
        if (params?.method && params.method !== 'ALL') queryParams.append('method', params.method);
        if (params?.tag?.trim()) queryParams.append('tag', params.tag.trim());
        if (params?.sourceName?.trim()) queryParams.append('source_name', params.sourceName.trim());
        if (params?.deprecated !== undefined) queryParams.append('deprecated', String(params.deprecated));

        return api.get<ApiAssetListResponse>(`/api-assets?${queryParams.toString()}`);
    },

    getApiIrStep: (assetId: string) => {
        return api.get<ApiIRStepResponse>(`/api-assets/${assetId}/api-ir-step`);
    },
};
