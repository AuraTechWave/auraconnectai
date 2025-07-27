/**
 * Shared TypeScript types for Payroll module
 * Centralized type definitions for maintainability and consistency
 */

// Base types
export interface Money {
  amount: number;
  currency?: string;
}

export interface DateRange {
  start: string;
  end: string;
}

// Staff related types
export interface StaffMember {
  id: number;
  name: string;
  email: string;
  hourly_rate: number;
  tax_status?: string;
  tenant_id?: number;
}

// Payroll calculation types
export interface PayrollHistory {
  id: number;
  staff_id: number;
  pay_period_start: string;
  pay_period_end: string;
  gross_pay: number;
  total_deductions: number;
  net_pay: number;
  status: PayrollStatus;
  processed_at: string;
  created_at?: string;
  updated_at?: string;
}

export interface PayrollDetail extends PayrollHistory {
  // Hours breakdown
  regular_hours: number;
  regular_pay: number;
  overtime_hours: number;
  overtime_pay: number;
  
  // Additional earnings
  bonuses: number;
  tips: number;
  commissions?: number;
  
  // Tax breakdown
  federal_tax: number;
  state_tax: number;
  local_tax?: number;
  social_security: number;
  medicare: number;
  
  // Other deductions
  other_deductions: Deduction[];
  
  // Employer contributions
  employer_contributions?: EmployerContribution[];
}

export interface Deduction {
  id?: number;
  description: string;
  amount: number;
  type: DeductionType;
  is_pretax: boolean;
}

export interface EmployerContribution {
  description: string;
  amount: number;
  type: string;
}

// Request/Response types
export interface PayrollRunRequest {
  staff_ids?: number[];
  pay_period_start: string;
  pay_period_end: string;
  tenant_id?: number;
  force_recalculate?: boolean;
  notify_employees?: boolean;
}

export interface PayrollRunResponse {
  job_id: string;
  status: JobStatus;
  total_staff: number;
  successful_count: number;
  failed_count: number;
  total_gross_pay: number;
  total_net_pay: number;
  created_at: string;
  estimated_completion?: string;
}

export interface PayrollHistoryResponse {
  staff_id: number;
  staff_name: string;
  payroll_history: PayrollHistory[];
  total_records: number;
  pagination?: PaginationInfo;
}

export interface PayrollRules {
  federal_tax_tables: TaxTable[];
  state_tax_tables: Record<string, TaxTable>;
  fica_rates: FICARates;
  overtime_rules: OvertimeRules;
  minimum_wage: Record<string, number>;
  updated_at: string;
}

export interface PayrollExportRequest {
  format: ExportFormat;
  pay_period_start?: string;
  pay_period_end?: string;
  staff_ids?: number[];
  include_details: boolean;
  tenant_id?: number;
}

export interface PayrollExportResponse {
  export_id: string;
  download_url: string;
  expires_at: string;
  format: ExportFormat;
  file_size: number;
}

// WebSocket event types
export interface PayrollWebSocketEvent {
  type: PayrollEventType;
  payload: any;
  timestamp: string;
}

export interface PayrollStatusUpdate {
  job_id: string;
  status: JobStatus;
  progress: number;
  message?: string;
  staff_id?: number;
  error?: string;
}

// Tax related types
export interface TaxTable {
  brackets: TaxBracket[];
  standard_deduction: number;
  personal_exemption: number;
  effective_date: string;
}

export interface TaxBracket {
  min: number;
  max: number | null;
  rate: number;
  base_tax: number;
}

export interface FICARates {
  social_security_rate: number;
  social_security_wage_base: number;
  medicare_rate: number;
  medicare_additional_rate: number;
  medicare_additional_threshold: number;
}

export interface OvertimeRules {
  daily_threshold?: number;
  weekly_threshold: number;
  multiplier: number;
  double_time_threshold?: number;
  double_time_multiplier?: number;
}

// Enums
export enum PayrollStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

export enum JobStatus {
  QUEUED = 'queued',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

export enum DeductionType {
  HEALTH_INSURANCE = 'health_insurance',
  DENTAL_INSURANCE = 'dental_insurance',
  VISION_INSURANCE = 'vision_insurance',
  RETIREMENT_401K = 'retirement_401k',
  RETIREMENT_IRA = 'retirement_ira',
  HSA = 'hsa',
  FSA = 'fsa',
  LIFE_INSURANCE = 'life_insurance',
  DISABILITY_INSURANCE = 'disability_insurance',
  GARNISHMENT = 'garnishment',
  LOAN_REPAYMENT = 'loan_repayment',
  UNION_DUES = 'union_dues',
  OTHER = 'other'
}

export enum ExportFormat {
  CSV = 'csv',
  EXCEL = 'excel',
  PDF = 'pdf',
  JSON = 'json',
  XML = 'xml'
}

export enum PayrollEventType {
  JOB_STARTED = 'payroll.job.started',
  JOB_PROGRESS = 'payroll.job.progress',
  JOB_COMPLETED = 'payroll.job.completed',
  JOB_FAILED = 'payroll.job.failed',
  STAFF_PROCESSED = 'payroll.staff.processed',
  STAFF_FAILED = 'payroll.staff.failed',
  EXPORT_READY = 'payroll.export.ready',
  ERROR = 'payroll.error'
}

// Utility types
export interface PaginationInfo {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
  };
}

// Type guards
export const isPayrollHistory = (obj: any): obj is PayrollHistory => {
  return obj && 
    typeof obj.id === 'number' &&
    typeof obj.staff_id === 'number' &&
    typeof obj.gross_pay === 'number' &&
    typeof obj.net_pay === 'number';
};

export const isPayrollDetail = (obj: any): obj is PayrollDetail => {
  return isPayrollHistory(obj) &&
    typeof obj.regular_hours === 'number' &&
    typeof obj.federal_tax === 'number' &&
    Array.isArray(obj.other_deductions);
};

export const isErrorResponse = (obj: any): obj is ErrorResponse => {
  return obj && obj.error && typeof obj.error.message === 'string';
};