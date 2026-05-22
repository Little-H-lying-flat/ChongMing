const API_VERSION_PATH = "/api/v1";
const DEFAULT_API_ORIGIN = "http://127.0.0.1:8000";
const ABSOLUTE_URL_PATTERN = /^https?:\/\//i;

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "");

export const API_ORIGIN = trimTrailingSlash(
    (process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_ORIGIN).replace(/\/api\/v1\/?$/, ""),
);

export const API_BASE_URL = `${API_ORIGIN}${API_VERSION_PATH}`;

export const buildApiUrl = (url: string): string => {
    if (ABSOLUTE_URL_PATTERN.test(url)) return url;

    const normalizedPath = url.startsWith("/") ? url : `/${url}`;
    const versionlessPath = normalizedPath.replace(/^\/api\/v1(?=\/|$)/, "") || "/";
    return `${API_BASE_URL}${versionlessPath}`;
};

const jsonHeaders = {
    "Content-Type": "application/json",
};

export const api = {
    fetch: (url: string, init?: RequestInit): Promise<Response> => {
        return fetch(buildApiUrl(url), init);
    },
    get: async <T>(url: string): Promise<{ data: T }> => {
        const res = await api.fetch(url, {
            method: "GET",
            headers: jsonHeaders,
            cache: "no-store",
        });

        if (!res.ok) {
            throw new Error(`API GET request failed with status: ${res.status}`);
        }
        const data = await res.json();
        return { data };
    },
    post: async <T>(url: string, body?: unknown): Promise<{ data: T }> => {
        const res = await api.fetch(url, {
            method: "POST",
            headers: jsonHeaders,
            body: body === undefined ? undefined : JSON.stringify(body),
        });

        if (!res.ok) {
            throw new Error(`API POST request failed with status: ${res.status}`);
        }
        const data = await res.json();
        return { data };
    },
    put: async <T>(url: string, body: unknown): Promise<{ data: T }> => {
        const res = await api.fetch(url, {
            method: "PUT",
            headers: jsonHeaders,
            body: JSON.stringify(body),
        });

        if (!res.ok) {
            throw new Error(`API PUT request failed with status: ${res.status}`);
        }
        const data = await res.json();
        return { data };
    },
    patch: async <T>(url: string, body: unknown): Promise<{ data: T }> => {
        const res = await api.fetch(url, {
            method: "PATCH",
            headers: jsonHeaders,
            body: JSON.stringify(body),
        });

        if (!res.ok) {
            throw new Error(`API PATCH request failed with status: ${res.status}`);
        }
        const data = await res.json();
        return { data };
    },
    delete: async (url: string): Promise<void> => {
        const res = await api.fetch(url, {
            method: "DELETE",
        });

        if (!res.ok) {
            throw new Error(`API DELETE request failed with status: ${res.status}`);
        }
    },
};

export default api;
