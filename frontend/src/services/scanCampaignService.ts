import api from './api';

export type JsonObject = Record<string, unknown>;

export interface ScanCampaignCreate {
    name: string;
    target: JsonObject;
    strategy: JsonObject;
    boundaries: JsonObject;
    action_policy: JsonObject;
    data_policy: JsonObject;
    special_limits: JsonObject;
}

export type ScanCampaignUpdate = Partial<ScanCampaignCreate>;

export interface ScanCampaign {
    id: string;
    name: string;
    status: string;
    target: JsonObject;
    strategy: JsonObject;
    boundaries: JsonObject;
    action_policy: JsonObject;
    data_policy: JsonObject;
    special_limits: JsonObject;
    ai_plan_id?: string | null;
    created_at: string;
    updated_at: string;
}

export interface ScanCampaignListResponse {
    items: ScanCampaign[];
    total: number;
    page: number;
    page_size: number;
}

export interface ReviewItem {
    id: string;
    campaign_id: string;
    plan_id: string;
    target_type: string;
    target_id: string;
    policy: string;
    title: string;
    reason: string;
    if_approved: string;
    if_rejected: string;
    available_choices: string[];
    choice: string;
    comment?: string | null;
    choice_updated_at?: string | null;
    created_at: string;
    updated_at: string;
}

export interface ScanCampaignPlan {
    plan_id: string;
    campaign_draft_id: string;
    version: number;
    status: string;
    summary: JsonObject;
    scope_review: JsonObject;
    ui_flows: JsonObject[];
    api_candidates: JsonObject[];
    risk_items: JsonObject[];
    manual_review_items: ReviewItem[];
    asset_drafts: JsonObject;
    coverage_summary: JsonObject;
    generation_metadata: JsonObject;
    created_at: string;
    updated_at: string;
}

export interface ReviewItemUpdateResponse {
    item: ReviewItem;
    plan_status: string;
}

export interface AssetDraft {
    id: string;
    campaign_id: string;
    plan_id: string;
    asset_type: string;
    source_type: string;
    source_item_id: string;
    policy: string;
    risk_level?: string | null;
    draft_payload: JsonObject;
    metadata: JsonObject;
    skipped_reason?: string | null;
    created_at: string;
}

export interface GenerateAssetDraftsResponse {
    api_case_ir_steps: JsonObject[];
    visual_ui_cases: JsonObject[];
    skipped_items: JsonObject[];
    asset_drafts: AssetDraft[];
}

export interface AssetDraftListResponse {
    items: AssetDraft[];
}

export interface AssetPromotion {
    id: string;
    campaign_id: string;
    plan_id: string;
    asset_draft_id: string;
    draft_type: string;
    generated_asset_type: string;
    generated_asset_id: string;
    status: string;
    promotion_metadata: JsonObject;
    created_at: string;
    updated_at: string;
}

export interface AssetPromotionListResponse {
    items: AssetPromotion[];
}

export interface PromoteAssetDraftResult {
    draft_id: string;
    asset_type: string;
    target_type?: string | null;
    target_id?: string | null;
    status: string;
    reason?: string | null;
}

export interface PromoteAssetDraftsResponse {
    promoted: PromoteAssetDraftResult[];
    duplicates: PromoteAssetDraftResult[];
    skipped: PromoteAssetDraftResult[];
    failed: PromoteAssetDraftResult[];
    execution_created: boolean;
}

export interface PromoteAssetDraftsRequest {
    draft_ids: string[];
    confirmation: 'PROMOTE_SELECTED_DRAFTS';
    allow_duplicates?: boolean;
    visual_project_id?: string;
}

export interface ConfirmExecutionRequest {
    promotion_ids: string[];
    confirmation: 'AUTHORIZE_SMART_SCAN_EXECUTION';
    mode?: string;
    engine?: string;
    parallel?: boolean;
    max_workers?: number;
    env?: string;
}

export interface ConfirmExecutionResponse {
    execution_created: boolean;
    execution_id: string;
    status: string;
    total_cases: number;
    dashboard_url: string;
    selected_promotions: string[];
    tc_ids: string[];
    dynamic_payload_count: number;
    skipped: JsonObject[];
}

export interface SmartScanExecutionSummaryItem {
    execution_id: string;
    status: string;
    total_cases: number;
    passed_cases: number;
    failed_cases: number;
    skipped_cases: number;
    pass_rate: number;
    duration_seconds?: number | null;
    dynamic_payload_count: number;
    created_at: string;
    updated_at: string;
}

export interface SmartScanExecutionSummaryResponse {
    campaign_id: string;
    plan_id: string;
    total_executions: number;
    latest_execution_id?: string | null;
    latest_status?: string | null;
    latest_created_at?: string | null;
    latest_updated_at?: string | null;
    executions: SmartScanExecutionSummaryItem[];
    result_breakdown: JsonObject;
    failure_categories: JsonObject[];
}

export interface SmartScanReportResponse {
    campaign_id: string;
    plan_id: string;
    generated_at: string;
    campaign: JsonObject;
    plan: JsonObject;
    review: JsonObject;
    assets: JsonObject;
    executions: JsonObject;
    recommendations: string[];
    markdown: string;
}

export interface ScanCampaignListParams {
    page?: number;
    pageSize?: number;
    status?: string;
    keyword?: string;
    scanMode?: string;
}

export const scanCampaignService = {
    listCampaigns: (params?: ScanCampaignListParams) => {
        const queryParams = new URLSearchParams();
        queryParams.append('page', (params?.page || 1).toString());
        queryParams.append('page_size', (params?.pageSize || 20).toString());

        if (params?.status?.trim()) queryParams.append('status', params.status.trim());
        if (params?.keyword?.trim()) queryParams.append('keyword', params.keyword.trim());
        if (params?.scanMode?.trim()) queryParams.append('scan_mode', params.scanMode.trim());

        return api.get<ScanCampaignListResponse>(`/scan-campaigns?${queryParams.toString()}`);
    },

    createCampaign: (payload: ScanCampaignCreate) => {
        return api.post<ScanCampaign>('/scan-campaigns', payload);
    },

    updateCampaign: (id: string, payload: ScanCampaignUpdate) => {
        return api.put<ScanCampaign>(`/scan-campaigns/${id}`, payload);
    },

    deleteCampaign: (id: string) => {
        return api.delete(`/scan-campaigns/${id}`);
    },

    generatePlan: (id: string, payload?: { regenerate?: boolean; notes?: string }) => {
        return api.post<ScanCampaignPlan>(`/scan-campaigns/${id}/generate-plan`, payload || {});
    },

    getLatestPlan: (id: string) => {
        return api.get<ScanCampaignPlan>(`/scan-campaigns/${id}/plan`);
    },

    updateReviewItem: (
        campaignId: string,
        planId: string,
        reviewItemId: string,
        payload: { choice: string; comment?: string },
    ) => {
        return api.patch<ReviewItemUpdateResponse>(
            `/scan-campaigns/${campaignId}/plans/${planId}/review-items/${reviewItemId}`,
            payload,
        );
    },

    generateAssetDrafts: (
        campaignId: string,
        planId: string,
        payload?: { asset_types?: string[]; include_only_approved?: boolean },
    ) => {
        return api.post<GenerateAssetDraftsResponse>(
            `/scan-campaigns/${campaignId}/plans/${planId}/generate-asset-drafts`,
            payload || { asset_types: ['api_case_ir', 'visual_ui_case'], include_only_approved: true },
        );
    },

    listAssetDrafts: (campaignId: string, planId: string) => {
        return api.get<AssetDraftListResponse>(`/scan-campaigns/${campaignId}/plans/${planId}/asset-drafts`);
    },

    listAssetPromotions: (campaignId: string, planId: string) => {
        return api.get<AssetPromotionListResponse>(`/scan-campaigns/${campaignId}/plans/${planId}/asset-drafts/promotions`);
    },

    promoteAssetDrafts: (campaignId: string, planId: string, payload: PromoteAssetDraftsRequest) => {
        return api.post<PromoteAssetDraftsResponse>(
            `/scan-campaigns/${campaignId}/plans/${planId}/promote-asset-drafts`,
            payload,
        );
    },

    confirmExecution: (campaignId: string, planId: string, payload: ConfirmExecutionRequest) => {
        return api.post<ConfirmExecutionResponse>(
            `/scan-campaigns/${campaignId}/plans/${planId}/confirm-execution`,
            payload,
        );
    },

    getExecutionSummary: (campaignId: string, planId: string) => {
        return api.get<SmartScanExecutionSummaryResponse>(
            `/scan-campaigns/${campaignId}/plans/${planId}/execution-summary`,
        );
    },

    getReport: (campaignId: string, planId: string) => {
        return api.get<SmartScanReportResponse>(`/scan-campaigns/${campaignId}/plans/${planId}/report`);
    },
};
