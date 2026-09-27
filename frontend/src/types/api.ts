export interface ApiResponse<T> {
  data: T;
  timestamp: string;
}

export interface ApiProblem {
  type?: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
  errorCode?: string;
  timestamp?: string;
  errors?: Record<string, string>;
}

export interface ServiceHealth {
  status: "UP" | "DOWN";
  service: string;
}
