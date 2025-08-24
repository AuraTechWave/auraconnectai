import React, { useState, useEffect, useRef } from 'react';
import { format, startOfWeek, endOfWeek } from 'date-fns';
import { schedulingService, PayrollSummary } from '../../../services/schedulingService';
import { usePermissions, PermissionGate } from '../../../hooks/usePermissions';
import { formatInRestaurantTz, getTimezoneAbbr } from '../../../utils/timezone';
import { FocusTrap, announce, KEYS } from '../../../utils/accessibility';
import './PayrollIntegration.css';

interface PayrollIntegrationProps {
  selectedDate: Date;
  onClose: () => void;
}

const PayrollIntegration: React.FC<PayrollIntegrationProps> = ({ selectedDate, onClose }) => {
  const [payrollData, setPayrollData] = useState<PayrollSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedStaff, setSelectedStaff] = useState<number[]>([]);
  const [payPeriod, setPayPeriod] = useState('weekly');
  const [exportFormat, setExportFormat] = useState<'pdf' | 'excel' | 'csv'>('pdf');
  
  const modalRef = useRef<HTMLDivElement>(null);
  const focusTrapRef = useRef<FocusTrap | null>(null);
  
  const { canViewPayroll, canExportPayroll } = usePermissions();
  
  const weekStart = startOfWeek(selectedDate, { weekStartsOn: 1 });
  const weekEnd = endOfWeek(selectedDate, { weekStartsOn: 1 });

  // Initialize focus trap
  useEffect(() => {
    if (modalRef.current && canViewPayroll) {
      focusTrapRef.current = new FocusTrap(modalRef.current);
      focusTrapRef.current.activate();
      
      // Announce modal opened
      announce('Payroll summary dialog opened', 'polite');
    }

    return () => {
      focusTrapRef.current?.deactivate();
    };
  }, [canViewPayroll]);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === KEYS.ESCAPE) {
        e.preventDefault();
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (canViewPayroll) {
      fetchPayrollData();
    }
  }, [selectedDate, selectedStaff, canViewPayroll]);

  const fetchPayrollData = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const data = await schedulingService.getPayrollSummary({
        start_date: weekStart.toISOString(),
        end_date: weekEnd.toISOString(),
        staff_ids: selectedStaff.length > 0 ? selectedStaff : undefined,
      });
      
      setPayrollData(data.summaries || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch payroll data');
      console.error('Error fetching payroll data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExport = async () => {
    if (!canExportPayroll) {
      setError('You do not have permission to export payroll data');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const blob = await schedulingService.exportPayrollReport({
        start_date: weekStart.toISOString(),
        end_date: weekEnd.toISOString(),
        format: exportFormat,
        staff_ids: selectedStaff.length > 0 ? selectedStaff : undefined,
      });

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `payroll-${format(weekStart, 'yyyy-MM-dd')}-to-${format(weekEnd, 'yyyy-MM-dd')}.${exportFormat}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      announce(`Payroll report exported as ${exportFormat.toUpperCase()}`, 'assertive');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export payroll data');
      console.error('Error exporting payroll:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const calculateTotals = () => {
    return payrollData.reduce(
      (totals, employee) => ({
        totalHours: totals.totalHours + employee.total_hours,
        regularHours: totals.regularHours + employee.regular_hours,
        overtimeHours: totals.overtimeHours + employee.overtime_hours,
        grossPay: totals.grossPay + employee.gross_pay,
        deductions: totals.deductions + employee.deductions,
        netPay: totals.netPay + employee.net_pay,
      }),
      {
        totalHours: 0,
        regularHours: 0,
        overtimeHours: 0,
        grossPay: 0,
        deductions: 0,
        netPay: 0,
      }
    );
  };

  if (!canViewPayroll) {
    return (
      <div className="payroll-modal">
        <div className="payroll-content" role="dialog" aria-modal="true" aria-labelledby="access-denied-title">
          <div className="payroll-header">
            <h2 id="access-denied-title">Access Denied</h2>
            <button className="close-button" onClick={onClose} aria-label="Close dialog">×</button>
          </div>
          <div className="payroll-body">
            <p className="error-message" role="alert">
              You do not have permission to view payroll information.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const totals = calculateTotals();
  const timezoneAbbr = getTimezoneAbbr();

  return (
    <div className="payroll-modal" role="presentation">
      <div ref={modalRef} className="payroll-content" role="dialog" aria-labelledby="payroll-title" aria-modal="true">
        <div className="payroll-header">
          <h2 id="payroll-title">
            Payroll Summary
            <span className="payroll-period">
              {formatInRestaurantTz(weekStart, 'MMM d')} - {formatInRestaurantTz(weekEnd, 'MMM d, yyyy')}
              <span className="timezone-indicator"> ({timezoneAbbr})</span>
            </span>
          </h2>
          <button 
            className="close-button" 
            onClick={onClose}
            aria-label="Close payroll summary"
          >
            ×
          </button>
        </div>

        {error && (
          <div className="error-banner" role="alert">
            <span className="error-icon">⚠️</span>
            {error}
          </div>
        )}

        <div className="payroll-body">
          {isLoading ? (
            <div className="loading-container" aria-busy="true" aria-live="polite">
              <div className="loading-spinner"></div>
              <p>Loading payroll data...</p>
            </div>
          ) : payrollData.length === 0 ? (
            <div className="empty-state">
              <p>No payroll data available for the selected period.</p>
            </div>
          ) : (
            <>
              <div className="payroll-table-container">
                <table className="payroll-table">
                  <thead>
                    <tr>
                      <th scope="col">Employee</th>
                      <th scope="col" className="hours-column">Regular Hours</th>
                      <th scope="col" className="hours-column">Overtime Hours</th>
                      <th scope="col" className="hours-column">Total Hours</th>
                      <th scope="col" className="amount-column">Gross Pay</th>
                      <th scope="col" className="amount-column">Deductions</th>
                      <th scope="col" className="amount-column">Net Pay</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payrollData.map((employee) => (
                      <tr key={employee.staff_id}>
                        <td>
                          <div className="employee-info">
                            <span className="employee-name">
                              {/* Name should come from the response */}
                              Staff #{employee.staff_id}
                            </span>
                          </div>
                        </td>
                        <td className="hours-column">{employee.regular_hours.toFixed(2)}</td>
                        <td className="hours-column">{employee.overtime_hours.toFixed(2)}</td>
                        <td className="hours-column total-hours">
                          {employee.total_hours.toFixed(2)}
                        </td>
                        <td className="amount-column">{formatCurrency(employee.gross_pay)}</td>
                        <td className="amount-column deductions">
                          {formatCurrency(employee.deductions)}
                        </td>
                        <td className="amount-column net-pay">
                          {formatCurrency(employee.net_pay)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="totals-row">
                      <th scope="row">Totals</th>
                      <td className="hours-column">{totals.regularHours.toFixed(2)}</td>
                      <td className="hours-column">{totals.overtimeHours.toFixed(2)}</td>
                      <td className="hours-column total-hours">
                        {totals.totalHours.toFixed(2)}
                      </td>
                      <td className="amount-column">{formatCurrency(totals.grossPay)}</td>
                      <td className="amount-column deductions">
                        {formatCurrency(totals.deductions)}
                      </td>
                      <td className="amount-column net-pay">
                        {formatCurrency(totals.netPay)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              <PermissionGate permission="payroll.export">
                <div className="payroll-actions">
                  <div className="export-options">
                    <label htmlFor="export-format">Export as:</label>
                    <select
                      id="export-format"
                      value={exportFormat}
                      onChange={(e) => {
                        setExportFormat(e.target.value as 'pdf' | 'excel' | 'csv');
                        announce(`Export format changed to ${e.target.value.toUpperCase()}`);
                      }}
                      className="export-select"
                    >
                      <option value="pdf">PDF</option>
                      <option value="excel">Excel</option>
                      <option value="csv">CSV</option>
                    </select>
                  </div>
                  <button
                    className="export-button"
                    onClick={handleExport}
                    disabled={isLoading}
                  >
                    {isLoading ? 'Exporting...' : 'Export Report'}
                  </button>
                </div>
              </PermissionGate>
            </>
          )}
        </div>

        <div className="payroll-footer">
          <p className="payroll-note">
            <strong>Note:</strong> All calculations are performed by the server. 
            This summary is for review purposes only. 
            {canExportPayroll && ' Exported reports include detailed breakdowns and are audit-logged.'}
          </p>
        </div>
      </div>
    </div>
  );
};

export default PayrollIntegration;