import api from './api';

export interface VisualStep {
    id?: string;
    step_index: number;
    action: 'GOTO' | 'CLICK' | 'TYPE' | 'WAIT' | 'ASSERT' | 'SCROLL';
    target_description?: string;
    value?: string;
    screenshot_baseline?: string;
}

export interface VisualUseCase {
    id: string;
    project_id: string;
    name: string;
    description?: string;
    status: 'draft' | 'active' | 'archived';
    base_url?: string;
    created_at: string;
    updated_at: string;
    steps: VisualStep[];
}

export type VisualCaseDraft = Omit<VisualUseCase, 'id' | 'created_at' | 'updated_at'>;

export interface VisualDraftRequest {
    prompt: string;
    project_id: string;
    base_url?: string;
}

export interface VisualDraftResponse {
    status: 'ok' | 'needs_clarification';
    draft?: VisualCaseDraft;
    questions: string[];
}

interface VisualExecutionStep {
    step_type: 'UI';
    action_type: string;
    description: string;
    target?: string;
    value?: string;
    url?: string;
    params: Record<string, string | number | boolean>;
}

export interface VisualExecutionPayload {
    tc_ids: string[];
    mode: 'normal';
    engine: 'right_pupil' | 'midscene';
    parallel: false;
    dynamic_payload: Array<{
        id: string;
        name: string;
        description?: string;
        mode: 'UI';
        steps: VisualExecutionStep[];
    }>;
}

const toExecutionAction = (action: VisualStep['action']) => action.toLowerCase();

export const buildVisualExecutionPayload = (visualCase: Pick<VisualUseCase, 'id' | 'name' | 'description' | 'base_url' | 'steps'>): VisualExecutionPayload => {
    const steps: VisualExecutionStep[] = visualCase.steps.map((step) => {
        const actionType = toExecutionAction(step.action);
        const description = step.target_description || step.value || step.action;
        const value = step.action === 'GOTO' ? (step.value || visualCase.base_url) : step.value;
        const params: Record<string, string | number | boolean> = step.action === 'TYPE' && step.value ? { text: step.value } : {};

        return {
            step_type: 'UI' as const,
            action_type: actionType,
            description,
            target: step.target_description,
            value,
            url: step.action === 'GOTO' ? value : undefined,
            params,
        };
    });

    return {
        tc_ids: [visualCase.id],
        mode: 'normal',
        engine: 'right_pupil',
        parallel: false,
        dynamic_payload: [{
            id: visualCase.id,
            name: visualCase.name,
            description: visualCase.description,
            mode: 'UI',
            steps,
        }],
    };
};

export const visualUiService = {
    // Get all cases (optionally by project ID)
    getCases: async (projectId?: string, skip: number = 0, limit: number = 20) => {
        const queryParams = new URLSearchParams();
        if (projectId) queryParams.append('project_id', projectId);
        queryParams.append('skip', skip.toString());
        queryParams.append('limit', limit.toString());

        return api.get<VisualUseCase[]>(`/visual-ui/cases?${queryParams.toString()}`);
    },

    // Get a single case by ID with its steps
    getCase: async (id: string) => {
        return api.get<VisualUseCase>(`/visual-ui/cases/${id}`);
    },

    // Create a new Visual UI test case
    createCase: async (data: Omit<VisualUseCase, 'id' | 'created_at' | 'updated_at'>) => {
        return api.post<VisualUseCase>('/visual-ui/cases', data);
    },

    // Update a Visual UI test case and overwrite steps
    updateCase: async (id: string, data: Partial<Omit<VisualUseCase, 'id' | 'created_at' | 'updated_at'>>) => {
        return api.put<VisualUseCase>(`/visual-ui/cases/${id}`, data);
    },

    // Delete a Visual UI test case
    deleteCase: async (id: string) => {
        return api.delete(`/visual-ui/cases/${id}`);
    },

    generateDraft: async (payload: VisualDraftRequest) => {
        return api.post<VisualDraftResponse>('/visual-ui/draft', payload);
    },

    // Helper trigger to instantly execute via existing Dispatch endpoint
    executeAdhoc: async (payload: VisualExecutionPayload | Record<string, unknown>) => {
        return api.post<Record<string, unknown>>('/executions', payload);
    },

    // Import and map from Neural Design
    importFromDesign: async (scenario: Record<string, unknown>) => {
        return api.post<{ status: string; visual_case_id: string }>('/visual-ui/import-from-design', scenario);
    }
};
