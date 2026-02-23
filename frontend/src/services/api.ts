const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

export const api = {
    get: async <T>(url: string): Promise<{ data: T }> => {
        const res = await fetch(`${API_BASE_URL}${url}`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
            cache: 'no-store',
        });

        if (!res.ok) {
            throw new Error(`API GET request failed with status: ${res.status}`);
        }
        const data = await res.json();
        return { data };
    },
    post: async <T>(url: string, body: any): Promise<{ data: T }> => {
        const res = await fetch(`${API_BASE_URL}${url}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(body),
        });

        if (!res.ok) {
            throw new Error(`API POST request failed with status: ${res.status}`);
        }
        const data = await res.json();
        return { data };
    },
    put: async <T>(url: string, body: any): Promise<{ data: T }> => {
        const res = await fetch(`${API_BASE_URL}${url}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(body),
        });

        if (!res.ok) {
            throw new Error(`API PUT request failed with status: ${res.status}`);
        }
        const data = await res.json();
        return { data };
    },
    delete: async (url: string): Promise<void> => {
        const res = await fetch(`${API_BASE_URL}${url}`, {
            method: "DELETE",
        });

        if (!res.ok) {
            throw new Error(`API DELETE request failed with status: ${res.status}`);
        }
    },
};

export default api;
