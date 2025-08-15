export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  roles: Role[];
  permissions: string[];
  created_at: string;
  updated_at: string;
  last_login?: string;
  profile?: UserProfile;
}

export interface Role {
  id: number;
  name: string;
  description: string;
  permissions: Permission[];
}

export interface Permission {
  id: number;
  name: string;
  resource: string;
  action: string;
  description: string;
}

export interface UserProfile {
  phone?: string;
  avatar_url?: string;
  department?: string;
  position?: string;
  hire_date?: string;
  employee_id?: string;
}
