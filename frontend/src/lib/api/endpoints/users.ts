import { apiClient } from '../client';
import type { User, UserCreate, UserUpdate, ProfileUpdate, PasswordChange } from '$lib/types/user';

export const usersAPI = {
  create: (data: UserCreate): Promise<User> => {
    return apiClient.post<User>('/api/v1/users/', data);
  },

  get: (id: string): Promise<User> => {
    return apiClient.get<User>(`/api/v1/users/${id}`);
  },

  me: (): Promise<User> => {
    return apiClient.get<User>('/api/v1/users/me');
  },

  list: (): Promise<User[]> => {
    return apiClient.get<User[]>('/api/v1/users/');
  },

  update: (userId: string, data: UserUpdate): Promise<User> => {
    return apiClient.put<User>(`/api/v1/users/${userId}`, data);
  },

  delete: (userId: string): Promise<void> => {
    return apiClient.delete(`/api/v1/users/${userId}`);
  },

  updateProfile: (data: ProfileUpdate): Promise<User> => {
    return apiClient.put<User>('/api/v1/users/me', data);
  },

  changePassword: (data: PasswordChange): Promise<void> => {
    return apiClient.put('/api/v1/users/me/password', data);
  },
};
