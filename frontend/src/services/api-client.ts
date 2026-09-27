import { getApiBaseUrl } from "@/lib/env";
import type { ApiProblem, ApiResponse, ServiceHealth } from "@/types/api";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly problem?: ApiProblem,
  ) {
    super(problem?.detail ?? `API request failed with status ${status}.`);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: `/${string}`,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init.headers,
    },
  });

  if (!response.ok) {
    const isJson = response.headers
      .get("content-type")
      ?.includes("application/problem+json");
    const problem = isJson
      ? ((await response.json()) as ApiProblem)
      : undefined;
    throw new ApiError(response.status, problem);
  }

  return (await response.json()) as T;
}

export const api = {
  getHealth(signal?: AbortSignal) {
    return request<ApiResponse<ServiceHealth>>("/api/v1/health", { signal });
  },
};
