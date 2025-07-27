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
          onCancel={() => setShowRunDialog(false)}
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
  const [payPeriodStart, setPayPeriodStart] = useState('');
  const [payPeriodEnd, setPayPeriodEnd] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
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
              onChange={(e) => setPayPeriodStart(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label>Pay Period End</label>
            <input
              type="date"
              value={payPeriodEnd}
              onChange={(e) => setPayPeriodEnd(e.target.value)}
              required
            />
          </div>
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