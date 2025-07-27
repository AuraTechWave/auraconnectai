/**
 * Payroll Integration Component for Staff Management UI
 * 
 * This component provides payroll functionality within the staff management interface,
 * including payroll history, running payroll, and viewing detailed breakdowns.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { usePayrollAPI, usePayrollWebSocket } from '../../hooks/usePayrollAPI';
import { usePayrollToast } from '../ui/Toast';
import { PayrollHistoryTableSkeleton, PayrollDetailSkeleton } from '../ui/SkeletonLoader';
import { 
  PayrollHistory, 
  PayrollRunRequest, 
  PayrollDetail,
  PayrollWebSocketEvent,
  PayrollEventType 
} from '../../types/payroll';

interface PayrollIntegrationProps {
  staffId: number;
  tenantId?: number;
}

export const PayrollIntegration: React.FC<PayrollIntegrationProps> = ({ staffId, tenantId }) => {
  const { 
    getPayrollHistory, 
    runPayroll, 
    getPayrollDetail,
    loading,
    error 
  } = usePayrollAPI();
  
  const { 
    runPayrollSuccess, 
    runPayrollError, 
    loadError, 
    payrollInfo 
  } = usePayrollToast();
  
  const [payrollHistory, setPayrollHistory] = useState<PayrollHistory[]>([]);
  const [selectedPayroll, setSelectedPayroll] = useState<number | null>(null);
  const [showRunDialog, setShowRunDialog] = useState(false);
  const [processingJobs, setProcessingJobs] = useState<Set<string>>(new Set());
  const runPayrollButtonRef = React.useRef<HTMLButtonElement>(null);

  const loadPayrollHistory = useCallback(async () => {
    try {
      const response = await getPayrollHistory(staffId, tenantId);
      setPayrollHistory(response.payroll_history);
    } catch (err) {
      loadError('payroll history');
    }
  }, [getPayrollHistory, staffId, tenantId, loadError]);

  // WebSocket integration for real-time updates
  const handleWebSocketUpdate = useCallback((event: PayrollWebSocketEvent) => {
    switch (event.type) {
      case PayrollEventType.JOB_STARTED:
        setProcessingJobs(prev => new Set([...prev, event.payload.job_id]));
        payrollInfo(`Payroll processing started: ${event.payload.job_id}`);
        break;
        
      case PayrollEventType.JOB_COMPLETED:
        setProcessingJobs(prev => {
          const updated = new Set(prev);
          updated.delete(event.payload.job_id);
          return updated;
        });
        payrollInfo('Payroll processing completed successfully');
        loadPayrollHistory(); // Refresh history
        break;
        
      case PayrollEventType.JOB_PROGRESS:
        // Update progress without full reload
        payrollInfo(`Processing progress: ${event.payload.completed_staff}/${event.payload.total_staff} staff members`);
        break;
        
      case PayrollEventType.JOB_FAILED:
        setProcessingJobs(prev => {
          const updated = new Set(prev);
          updated.delete(event.payload.job_id);
          return updated;
        });
        runPayrollError(`Processing failed: ${event.payload.error}`);
        break;
        
      case PayrollEventType.STAFF_PROCESSED:
        if (event.payload.staff_id === staffId) {
          payrollInfo(`Payroll processed for staff member`);
        }
        break;
        
      default:
        console.log('Unhandled payroll event:', event);
    }
  }, [staffId, payrollInfo, runPayrollError, loadPayrollHistory]);

  const { connected, connectionStatus } = usePayrollWebSocket(handleWebSocketUpdate, staffId);

  useEffect(() => {
    loadPayrollHistory();
  }, [loadPayrollHistory]);

  const handleRunPayroll = async (request: PayrollRunRequest) => {
    try {
      const result = await runPayroll({
        ...request,
        staff_ids: [staffId],
        tenant_id: tenantId
      });
      
      runPayrollSuccess(result.total_staff);
      setShowRunDialog(false);
      
      // Show processing info with job ID
      payrollInfo(`Processing job: ${result.job_id}`);
      
      // Reload history after a delay to show new payroll
      setTimeout(() => loadPayrollHistory(), 2000);
    } catch (err) {
      runPayrollError(err instanceof Error ? err.message : 'Unknown error occurred');
    }
  };

  return (
    <div className="payroll-integration">
      <div className="payroll-header">
        <h3>Payroll Information</h3>
        <div className="header-actions">
          {/* Real-time connection indicator */}
          <div className={`connection-status connection-status--${connectionStatus}`}>
            <span className="status-indicator" />
            {connectionStatus === 'connected' && 'Live'}
            {connectionStatus === 'connecting' && 'Connecting...'}
            {connectionStatus === 'error' && 'Reconnecting...'}
            {connectionStatus === 'disconnected' && 'Offline'}
          </div>
          
          {/* Processing indicator */}
          {processingJobs.size > 0 && (
            <div className="processing-indicator">
              <span className="spinner" />
              Processing {processingJobs.size} job{processingJobs.size > 1 ? 's' : ''}
            </div>
          )}
          
          <button 
            ref={runPayrollButtonRef}
            className="btn-primary"
            onClick={() => setShowRunDialog(true)}
            disabled={loading}
          >
            Run Payroll
          </button>
        </div>
      </div>

      {loading ? (
        <PayrollHistoryTableSkeleton />
      ) : payrollHistory.length === 0 ? (
        <div className="empty-state">
          <p>No payroll history available for this staff member.</p>
          <p>Click "Run Payroll" to process the first payroll.</p>
        </div>
      ) : (
        <>
          <PayrollHistoryTable 
            history={payrollHistory}
            onSelectPayroll={setSelectedPayroll}
          />
          
          {selectedPayroll && (
            <PayrollDetailView 
              payrollId={selectedPayroll}
              onClose={() => setSelectedPayroll(null)}
            />
          )}
        </>
      )}

      {showRunDialog && (
        <RunPayrollDialog
          staffId={staffId}
          onConfirm={handleRunPayroll}
          onCancel={() => {
            setShowRunDialog(false);
            // Return focus to the run payroll button
            setTimeout(() => runPayrollButtonRef.current?.focus(), 100);
          }}
        />
      )}
    </div>
  );
};

interface PayrollHistoryTableProps {
  history: PayrollHistory[];
  onSelectPayroll: (id: number) => void;
}

const PayrollHistoryTable: React.FC<PayrollHistoryTableProps> = ({ history, onSelectPayroll }) => {
  return (
    <table className="payroll-history-table">
      <thead>
        <tr>
          <th>Pay Period</th>
          <th>Gross Pay</th>
          <th>Deductions</th>
          <th>Net Pay</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {history.map((payroll) => (
          <tr key={payroll.id}>
            <td>{formatPayPeriod(payroll.pay_period_start, payroll.pay_period_end)}</td>
            <td>${payroll.gross_pay.toFixed(2)}</td>
            <td>${payroll.total_deductions.toFixed(2)}</td>
            <td>${payroll.net_pay.toFixed(2)}</td>
            <td>
              <span className={`status ${payroll.status}`}>
                {payroll.status}
              </span>
            </td>
            <td>
              <button onClick={() => onSelectPayroll(payroll.id)}>
                View Details
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};

interface RunPayrollDialogProps {
  staffId: number;
  onConfirm: (request: PayrollRunRequest) => void;
  onCancel: () => void;
}

const RunPayrollDialog: React.FC<RunPayrollDialogProps> = ({ staffId, onConfirm, onCancel }) => {
  // Default to current bi-weekly period
  const getDefaultPeriod = () => {
    const today = new Date();
    const dayOfWeek = today.getDay();
    const daysToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
    
    // Get the most recent Monday
    const periodStart = new Date(today);
    periodStart.setDate(today.getDate() + daysToMonday);
    
    // If today is Monday and we haven't started the day, use previous period
    if (dayOfWeek === 1 && today.getHours() < 12) {
      periodStart.setDate(periodStart.getDate() - 14);
    }
    
    // Calculate end date (2 weeks minus 1 day)
    const periodEnd = new Date(periodStart);
    periodEnd.setDate(periodStart.getDate() + 13);
    
    return {
      start: periodStart.toISOString().split('T')[0],
      end: periodEnd.toISOString().split('T')[0]
    };
  };

  const defaultPeriod = getDefaultPeriod();
  const [payPeriodStart, setPayPeriodStart] = useState(defaultPeriod.start);
  const [payPeriodEnd, setPayPeriodEnd] = useState(defaultPeriod.end);
  const [dateError, setDateError] = useState('');

  const validateDates = () => {
    const start = new Date(payPeriodStart);
    const end = new Date(payPeriodEnd);
    
    if (end <= start) {
      setDateError('End date must be after start date');
      return false;
    }
    
    const daysDiff = Math.floor((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
    if (daysDiff > 31) {
      setDateError('Pay period cannot exceed 31 days');
      return false;
    }
    
    setDateError('');
    return true;
  };

  const handleStartDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPayPeriodStart(e.target.value);
    setDateError(''); // Clear error on change
  };

  const handleEndDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPayPeriodEnd(e.target.value);
    setDateError(''); // Clear error on change
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateDates()) {
      return;
    }
    
    onConfirm({
      staff_ids: [staffId],
      pay_period_start: payPeriodStart,
      pay_period_end: payPeriodEnd,
      force_recalculate: false
    });
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h3>Run Payroll</h3>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Pay Period Start</label>
            <input
              type="date"
              value={payPeriodStart}
              onChange={handleStartDateChange}
              required
            />
          </div>
          <div className="form-group">
            <label>Pay Period End</label>
            <input
              type="date"
              value={payPeriodEnd}
              onChange={handleEndDateChange}
              required
            />
          </div>
          {dateError && (
            <div className="form-error" role="alert">
              {dateError}
            </div>
          )}
          <div className="form-actions">
            <button type="submit" className="btn-primary">
              Run Payroll
            </button>
            <button type="button" onClick={onCancel}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

interface PayrollDetailViewProps {
  payrollId: number;
  onClose: () => void;
}

const PayrollDetailView: React.FC<PayrollDetailViewProps> = ({ payrollId, onClose }) => {
  const { getPayrollDetail } = usePayrollAPI();
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDetail();
  }, [payrollId]);

  const loadDetail = async () => {
    try {
      setLoading(true);
      const data = await getPayrollDetail(payrollId);
      setDetail(data);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div>Loading payroll details...</div>;
  if (!detail) return null;

  return (
    <div className="payroll-detail-view">
      <div className="detail-header">
        <h4>Payroll Detail</h4>
        <button onClick={onClose}>×</button>
      </div>
      
      <div className="detail-content">
        <section>
          <h5>Earnings</h5>
          <table>
            <tbody>
              <tr>
                <td>Regular Hours ({detail.regular_hours})</td>
                <td>${detail.regular_pay.toFixed(2)}</td>
              </tr>
              <tr>
                <td>Overtime Hours ({detail.overtime_hours})</td>
                <td>${detail.overtime_pay.toFixed(2)}</td>
              </tr>
              {detail.bonuses > 0 && (
                <tr>
                  <td>Bonuses</td>
                  <td>${detail.bonuses.toFixed(2)}</td>
                </tr>
              )}
              {detail.tips > 0 && (
                <tr>
                  <td>Tips</td>
                  <td>${detail.tips.toFixed(2)}</td>
                </tr>
              )}
              <tr className="total">
                <td>Gross Pay</td>
                <td>${detail.gross_pay.toFixed(2)}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section>
          <h5>Deductions</h5>
          <table>
            <tbody>
              <tr>
                <td>Federal Tax</td>
                <td>-${detail.federal_tax.toFixed(2)}</td>
              </tr>
              <tr>
                <td>State Tax</td>
                <td>-${detail.state_tax.toFixed(2)}</td>
              </tr>
              <tr>
                <td>Social Security</td>
                <td>-${detail.social_security.toFixed(2)}</td>
              </tr>
              <tr>
                <td>Medicare</td>
                <td>-${detail.medicare.toFixed(2)}</td>
              </tr>
              {detail.other_deductions.map((ded: any, idx: number) => (
                <tr key={idx}>
                  <td>{ded.description}</td>
                  <td>-${ded.amount.toFixed(2)}</td>
                </tr>
              ))}
              <tr className="total">
                <td>Total Deductions</td>
                <td>-${detail.total_deductions.toFixed(2)}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <div className="net-pay">
          <h5>Net Pay</h5>
          <div className="amount">${detail.net_pay.toFixed(2)}</div>
        </div>
      </div>
    </div>
  );
};

// Utility functions
const formatPayPeriod = (start: string, end: string): string => {
  const startDate = new Date(start);
  const endDate = new Date(end);
  return `${startDate.toLocaleDateString()} - ${endDate.toLocaleDateString()}`;
};

export default PayrollIntegration;