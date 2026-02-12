export interface Action {
    action_type: string;
    target: {
        strategy: string;
        value: string;
        description?: string;
    };
    params?: Record<string, any>;
    expected_visual_change?: string;
}

export interface TraceLog {
    step: number;
    action: Action;
    status: string;
    error?: string;
    coords?: { x: number; y: number };
    stable_selector?: string;
    details?: string;
    timestamp?: string;
}

export type ExecutionResult = TraceLog[];

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

/**
 * Run a UI Automation Task (Right Pupil)
 */
export async function runUiTask(prompt: string, url: string): Promise<ExecutionResult> {
    try {
        const response = await fetch(`${API_BASE_URL}/executions/ui/run`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ prompt, url }),
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API Error ${response.status}: ${errorText}`);
        }

        const data: ExecutionResult = await response.json();
        return data;
    } catch (error) {
        console.error('Failed to run UI task:', error);
        throw error;
    }
}
