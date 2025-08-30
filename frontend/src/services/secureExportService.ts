import api from './api';
import { tenantService } from './tenantService';

export interface ExportOptions {
  format: 'csv' | 'xlsx' | 'pdf';
  includeHeaders?: boolean;
  dateRange?: {
    start: string;
    end: string;
  };
  filters?: Record<string, any>;
  redactPII?: boolean;
  compressionLevel?: 'none' | 'low' | 'high';
}

export interface ExportResult {
  exportId: string;
  downloadUrl: string;
  expiresAt: string;
  size: number;
  checksum: string;
}

export interface AuditLog {
  id: string;
  userId: string;
  action: string;
  resourceType: string;
  resourceId?: string;
  timestamp: string;
  ipAddress: string;
  userAgent: string;
  details: Record<string, any>;
}

class SecureExportService {
  private pendingExports = new Map<string, AbortController>();

  /**
   * Request secure export with role validation and audit logging
   */
  async requestExport(
    resourceType: string,
    resourceId: string | null,
    options: ExportOptions,
    requiredRole?: string
  ): Promise<ExportResult> {
    // Create abort controller for cancellation
    const abortController = new AbortController();
    const exportId = this.generateExportId();
    this.pendingExports.set(exportId, abortController);

    try {
      // Get tenant context
      const tenant = tenantService.getCurrentTenant();
      if (!tenant) {
        throw new Error('No tenant context available');
      }

      // Build secure export request
      const exportRequest = {
        resourceType,
        resourceId,
        tenantId: tenant.id,
        options: {
          ...options,
          redactPII: options.redactPII ?? true, // Default to redacting PII
        },
        requiredRole,
        timestamp: new Date().toISOString(),
        requestId: exportId,
      };

      // Request export from server (role validation happens server-side)
      const response = await api.post(
        '/api/exports/request',
        exportRequest,
        {
          signal: abortController.signal,
          headers: {
            'X-Export-Type': resourceType,
            'X-Tenant-Id': tenant.id,
          },
        }
      );

      const result: ExportResult = response.data;

      // Log successful export
      await this.logExportAudit({
        action: 'export.requested',
        resourceType,
        resourceId,
        details: {
          format: options.format,
          exportId: result.exportId,
          size: result.size,
        },
      });

      return result;
    } catch (error: any) {
      // Log failed export attempt
      await this.logExportAudit({
        action: 'export.failed',
        resourceType,
        resourceId,
        details: {
          error: error.message,
          format: options.format,
        },
      });

      throw error;
    } finally {
      this.pendingExports.delete(exportId);
    }
  }

  /**
   * Download exported file with secure signed URL
   */
  async downloadExport(exportResult: ExportResult): Promise<Blob> {
    try {
      // Validate export hasn't expired
      if (new Date(exportResult.expiresAt) < new Date()) {
        throw new Error('Export link has expired');
      }

      // Download from signed URL
      const response = await api.get(exportResult.downloadUrl, {
        responseType: 'blob',
        headers: {
          'X-Export-Id': exportResult.exportId,
        },
      });

      // Verify checksum if provided
      if (exportResult.checksum) {
        const isValid = await this.verifyChecksum(response.data, exportResult.checksum);
        if (!isValid) {
          throw new Error('Export file integrity check failed');
        }
      }

      // Log successful download
      await this.logExportAudit({
        action: 'export.downloaded',
        resourceType: 'export',
        resourceId: exportResult.exportId,
        details: {
          size: exportResult.size,
        },
      });

      return response.data;
    } catch (error: any) {
      // Log failed download
      await this.logExportAudit({
        action: 'export.download_failed',
        resourceType: 'export',
        resourceId: exportResult.exportId,
        details: {
          error: error.message,
        },
      });

      throw error;
    }
  }

  /**
   * Cancel pending export
   */
  cancelExport(exportId: string): void {
    const controller = this.pendingExports.get(exportId);
    if (controller) {
      controller.abort();
      this.pendingExports.delete(exportId);
    }
  }

  /**
   * Get export audit logs
   */
  async getExportAuditLogs(
    filters?: {
      userId?: string;
      resourceType?: string;
      startDate?: string;
      endDate?: string;
      action?: string;
    }
  ): Promise<AuditLog[]> {
    const response = await api.get('/api/audit/exports', {
      params: filters,
    });

    return response.data;
  }

  /**
   * Verify file checksum
   */
  private async verifyChecksum(blob: Blob, expectedChecksum: string): Promise<boolean> {
    try {
      const arrayBuffer = await blob.arrayBuffer();
      const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
      
      return hashHex === expectedChecksum;
    } catch {
      // If crypto API not available, skip verification
      return true;
    }
  }

  /**
   * Log export audit event
   */
  private async logExportAudit(event: {
    action: string;
    resourceType: string;
    resourceId?: string | null;
    details: Record<string, any>;
  }): Promise<void> {
    try {
      await api.post('/api/audit/log', {
        ...event,
        timestamp: new Date().toISOString(),
        source: 'export-service',
      });
    } catch (error) {
      // Don't fail export if audit logging fails, but log to console
      console.error('Failed to log export audit:', error);
    }
  }

  /**
   * Generate unique export ID
   */
  private generateExportId(): string {
    return `exp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Export with data redaction
   */
  async exportWithRedaction<T extends Record<string, any>>(
    data: T[],
    piiFields: string[],
    options: ExportOptions
  ): Promise<ExportResult> {
    // Redact PII fields if requested
    const processedData = options.redactPII
      ? this.redactPIIFields(data, piiFields)
      : data;

    // Send to server for export generation
    return this.requestExport('custom', null, {
      ...options,
      filters: {
        data: processedData,
      },
    });
  }

  /**
   * Redact PII fields from data
   */
  private redactPIIFields<T extends Record<string, any>>(
    data: T[],
    piiFields: string[]
  ): T[] {
    return data.map(item => {
      const redacted = { ...item };
      
      piiFields.forEach(field => {
        if (field in redacted) {
          // Redact based on field type
          if (typeof redacted[field] === 'string') {
            if (field.toLowerCase().includes('email')) {
              // Partial email redaction
              (redacted as any)[field] = this.redactEmail((redacted as any)[field]);
            } else if (field.toLowerCase().includes('phone')) {
              // Partial phone redaction
              (redacted as any)[field] = this.redactPhone((redacted as any)[field]);
            } else if (field.toLowerCase().includes('ssn') || field.toLowerCase().includes('social')) {
              // Full SSN redaction
              (redacted as any)[field] = '***-**-****';
            } else {
              // Generic redaction
              (redacted as any)[field] = '***';
            }
          } else if (typeof redacted[field] === 'number') {
            (redacted as any)[field] = 0;
          }
        }
      });

      return redacted;
    });
  }

  /**
   * Redact email keeping domain
   */
  private redactEmail(email: string): string {
    const [local, domain] = email.split('@');
    if (!domain) return '***';
    
    const redactedLocal = local.substring(0, 2) + '***';
    return `${redactedLocal}@${domain}`;
  }

  /**
   * Redact phone keeping area code
   */
  private redactPhone(phone: string): string {
    const cleaned = phone.replace(/\D/g, '');
    if (cleaned.length < 10) return '***';
    
    return `${cleaned.substring(0, 3)}-***-****`;
  }
}

export const secureExportService = new SecureExportService();
export default secureExportService;