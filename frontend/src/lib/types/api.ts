// Common API types

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface ErrorResponse {
  detail: string;
  [key: string]: any;
}

export interface SuccessResponse {
  message: string;
}
