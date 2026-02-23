import api from './api';

export interface KPIParams {
    total_executions: number;
    global_pass_rate: string;
    active_environments: number;
    omniparser_status: string;
    db_status: string;
}

export interface TrendData {
    date: string;
    passed: number;
    failed: number;
}

export interface DefectData {
    name: string;
    value: number;
}

export interface RecentActivity {
    id: string;
    scenario: string;
    status: string;
    time: string;
    duration: string;
    error?: string;
}

export interface DashboardResponse {
    kpis: KPIParams;
    trend: TrendData[];
    defects: DefectData[];
    recent_activities: RecentActivity[];
}

export const getDashboardOverview = async (): Promise<DashboardResponse> => {
    const response = await api.get<DashboardResponse>('/dashboard/overview');
    return response.data;
};
