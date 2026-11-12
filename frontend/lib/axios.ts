import axios, {
    AxiosError,
    InternalAxiosRequestConfig,
} from "axios";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

const api = axios.create({
    baseURL: API_BASE_URL,
    withCredentials: true,
});

interface RetryableRequestConfig extends InternalAxiosRequestConfig {
    _retry?: boolean;
}

let refreshPromise: Promise<void> | null = null;


const refreshSession = (): Promise<void> => {
    if (!refreshPromise) {
        refreshPromise = api
            .post(
                "/auth/refresh",
                {},
                {
                    withCredentials: true,
                }
            )
            .then(() => undefined)
            .finally(() => {
                refreshPromise = null;
            });
    }

    return refreshPromise;
};



api.interceptors.response.use(
    (response) => response,

    async (error: AxiosError) => {
        const originalRequest =
            error.config as RetryableRequestConfig | undefined;

        if (!originalRequest || error.response?.status !== 401) {
            return Promise.reject(error);
        }

        if (typeof window === "undefined") {
            return Promise.reject(error);
        }

        const url = originalRequest.url ?? "";
        const isAuthEndpoint =
            url.includes("/auth/login") ||
            url.includes("/auth/register") ||
            url.includes("/auth/refresh");

        if (isAuthEndpoint || originalRequest._retry) {
            return Promise.reject(error);
        }

        originalRequest._retry = true;

        try {
            await refreshSession();
            return api(originalRequest);
        } catch (refreshError) {
            window.location.replace("/login?reason=expired");
            return Promise.reject(refreshError);
        }
    }
);

export default api;
