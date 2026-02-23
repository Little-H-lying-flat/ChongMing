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

    // Helper trigger to instantly execute via existing Dispatch endpoint
    executeAdhoc: async (payload: any) => {
        return api.post<any>('/executions', payload);
    },

    // Import and map from Neural Design
    importFromDesign: async (scenario: any) => {
        return api.post<{ status: string; visual_case_id: string }>('/visual-ui/import-from-design', scenario);
    }
};
