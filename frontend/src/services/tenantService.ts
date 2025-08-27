import api from './api';

export interface Tenant {
  id: string;
  name: string;
  timezone: string;
  currency: string;
  locale: string;
  settings: Record<string, any>;
}

export interface TenantAccess {
  tenantId: string;
  role: string;
  permissions: string[];
}

class TenantService {
  private currentTenant: Tenant | null = null;
  private tenantCache = new Map<string, Tenant>();

  async validateAccess(tenantId: string): Promise<boolean> {
    try {
      const response = await api.get(`/api/tenants/${tenantId}/validate-access`);
      return response.data.hasAccess;
    } catch (error) {
      console.error('Failed to validate tenant access:', error);
      return false;
    }
  }

  async getTenant(tenantId: string): Promise<Tenant | null> {
    // Check cache first
    if (this.tenantCache.has(tenantId)) {
      return this.tenantCache.get(tenantId)!;
    }

    try {
      const response = await api.get(`/api/tenants/${tenantId}`);
      const tenant = response.data;
      this.tenantCache.set(tenantId, tenant);
      return tenant;
    } catch (error) {
      console.error('Failed to fetch tenant:', error);
      return null;
    }
  }

  async setCurrentTenant(tenantId: string): Promise<void> {
    const tenant = await this.getTenant(tenantId);
    if (tenant) {
      this.currentTenant = tenant;
      // Store in session storage for persistence
      sessionStorage.setItem('currentTenantId', tenantId);
      // Dispatch event for other components to react
      window.dispatchEvent(new CustomEvent('tenant:changed', { detail: tenant }));
    }
  }

  getCurrentTenant(): Tenant | null {
    return this.currentTenant;
  }

  async getUserTenants(): Promise<TenantAccess[]> {
    try {
      const response = await api.get('/api/users/me/tenants');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch user tenants:', error);
      return [];
    }
  }

  clearTenantContext(): void {
    this.currentTenant = null;
    sessionStorage.removeItem('currentTenantId');
    this.tenantCache.clear();
  }

  // Scope API calls to current tenant
  getScopedUrl(path: string): string {
    if (!this.currentTenant) {
      throw new Error('No tenant context set');
    }
    return `/api/tenants/${this.currentTenant.id}${path}`;
  }
}

export const tenantService = new TenantService();
export default tenantService;