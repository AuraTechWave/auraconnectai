import React, { useState, useEffect } from 'react';
import { format, parseISO, startOfWeek, endOfWeek, differenceInHours } from 'date-fns';
import './PayrollIntegration.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const PayrollIntegration = ({ shifts, staff, selectedDate, onClose }) => {
  const [payrollData, setPayrollData] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedStaff, setSelectedStaff] = useState([]);
  const [payPeriod, setPayPeriod] = useState('weekly');
  const [includeOvertime, setIncludeOvertime] = useState(true);
  const [includeBenefits, setIncludeBenefits] = useState(true);
  const [payrollSummary, setPayrollSummary] = useState(null);
  const [exportFormat, setExportFormat] = useState('pdf');

  const weekStart = startOfWeek(selectedDate, { weekStartsOn: 1 });
  const weekEnd = endOfWeek(selectedDate, { weekStartsOn: 1 });

  useEffect(() => {
    calculatePayrollData();
  }, [shifts, selectedStaff, includeOvertime, includeBenefits]);

  const calculatePayrollData = () => {
    const data = staff.map(member => {
      const staffShifts = shifts.filter(s => 
        s.staff_id === member.id && 
        (selectedStaff.length === 0 || selectedStaff.includes(member.id))
      );

      let regularHours = 0;
      let overtimeHours = 0;
      let holidayHours = 0;
      let totalPay = 0;

      staffShifts.forEach(shift => {
        const hours = differenceInHours(
          parseISO(shift.end_time),
          parseISO(shift.start_time)
        );

        const hourlyRate = shift.hourly_rate || member.hourly_rate || 15;

        switch (shift.shift_type) {
          case 'REGULAR':
            if (regularHours + hours > 40 && includeOvertime) {
              const regularPortion = Math.max(0, 40 - regularHours);
              const overtimePortion = hours - regularPortion;
              regularHours += regularPortion;
              overtimeHours += overtimePortion;
              totalPay += regularPortion * hourlyRate + overtimePortion * hourlyRate * 1.5;
            } else {
              regularHours += hours;
              totalPay += hours * hourlyRate;
            }
            break;
          case 'OVERTIME':
            overtimeHours += hours;
            totalPay += hours * hourlyRate * 1.5;
            break;
          case 'HOLIDAY':
            holidayHours += hours;
            totalPay += hours * hourlyRate * 2;
            break;
          default:
            regularHours += hours;
            totalPay += hours * hourlyRate;
        }
      });

      // Calculate deductions
      const federalTax = totalPay * 0.15;
      const stateTax = totalPay * 0.05;
      const socialSecurity = totalPay * 0.062;
      const medicare = totalPay * 0.0145;
      const totalDeductions = federalTax + stateTax + socialSecurity + medicare;

      // Benefits (if included)
      let benefits = 0;
      if (includeBenefits && regularHours >= 30) {
        benefits = 200; // Health insurance contribution
      }

      const netPay = totalPay - totalDeductions;

      return {
        id: member.id,
        name: member.name,
        role: member.role,
        regularHours,
        overtimeHours,
        holidayHours,
        totalHours: regularHours + overtimeHours + holidayHours,
        hourlyRate: member.hourly_rate || 15,
        grossPay: totalPay,
        federalTax,
        stateTax,
        socialSecurity,
        medicare,
        totalDeductions,
        benefits,
        netPay,
        shiftsCount: staffShifts.length
      };
    }).filter(data => data.shiftsCount > 0);

    setPayrollData(data);

    // Calculate summary
    const summary = {
      totalStaff: data.length,
      totalHours: data.reduce((sum, d) => sum + d.totalHours, 0),
      totalRegularHours: data.reduce((sum, d) => sum + d.regularHours, 0),
      totalOvertimeHours: data.reduce((sum, d) => sum + d.overtimeHours, 0),
      totalGrossPay: data.reduce((sum, d) => sum + d.grossPay, 0),
      totalDeductions: data.reduce((sum, d) => sum + d.totalDeductions, 0),
      totalBenefits: data.reduce((sum, d) => sum + d.benefits, 0),
      totalNetPay: data.reduce((sum, d) => sum + d.netPay, 0)
    };

    setPayrollSummary(summary);
  };

  const handleStaffSelection = (staffId) => {
    if (selectedStaff.includes(staffId)) {
      setSelectedStaff(selectedStaff.filter(id => id !== staffId));
    } else {
      setSelectedStaff([...selectedStaff, staffId]);
    }
  };

  const handleSelectAll = () => {
    if (selectedStaff.length === staff.length) {
      setSelectedStaff([]);
    } else {
      setSelectedStaff(staff.map(s => s.id));
    }
  };

  const handleProcessPayroll = async () => {
    if (payrollData.length === 0) {
      alert('No payroll data to process');
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/staff/payroll/process`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            pay_period_start: format(weekStart, 'yyyy-MM-dd'),
            pay_period_end: format(weekEnd, 'yyyy-MM-dd'),
            staff_ids: selectedStaff.length > 0 ? selectedStaff : staff.map(s => s.id),
            include_overtime: includeOvertime,
            include_benefits: includeBenefits,
            auto_approve: false
          })
        }
      );

      if (!response.ok) throw new Error('Failed to process payroll');
      
      const result = await response.json();
      alert(`Payroll processed successfully! Batch ID: ${result.batch_id}`);
      
      // Export payroll report
      await exportPayrollReport();
    } catch (err) {
      console.error('Failed to process payroll:', err);
      alert('Failed to process payroll. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const exportPayrollReport = async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/staff/payroll/export?start_date=${format(weekStart, 'yyyy-MM-dd')}&end_date=${format(weekEnd, 'yyyy-MM-dd')}&format=${exportFormat}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      );

      if (!response.ok) throw new Error('Failed to export payroll report');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `payroll-${format(weekStart, 'yyyy-MM-dd')}.${exportFormat}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Failed to export payroll report:', err);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="payroll-integration" onClick={e => e.stopPropagation()}>
        <div className="payroll-header">
          <h2>Payroll Integration</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="payroll-controls">
          <div className="control-group">
            <label>Pay Period</label>
            <select 
              value={payPeriod} 
              onChange={(e) => setPayPeriod(e.target.value)}
            >
              <option value="weekly">Weekly</option>
              <option value="biweekly">Bi-weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>

          <div className="control-group">
            <label>
              <input
                type="checkbox"
                checked={includeOvertime}
                onChange={(e) => setIncludeOvertime(e.target.checked)}
              />
              Include Overtime Calculations
            </label>
          </div>

          <div className="control-group">
            <label>
              <input
                type="checkbox"
                checked={includeBenefits}
                onChange={(e) => setIncludeBenefits(e.target.checked)}
              />
              Include Benefits
            </label>
          </div>

          <div className="control-group">
            <label>Export Format</label>
            <select 
              value={exportFormat} 
              onChange={(e) => setExportFormat(e.target.value)}
            >
              <option value="pdf">PDF Report</option>
              <option value="excel">Excel Spreadsheet</option>
              <option value="csv">CSV File</option>
            </select>
          </div>
        </div>

        <div className="payroll-summary">
          <h3>Payroll Summary for {format(weekStart, 'MMM d')} - {format(weekEnd, 'MMM d, yyyy')}</h3>
          {payrollSummary && (
            <div className="summary-cards">
              <div className="summary-card">
                <div className="card-label">Total Staff</div>
                <div className="card-value">{payrollSummary.totalStaff}</div>
              </div>
              <div className="summary-card">
                <div className="card-label">Total Hours</div>
                <div className="card-value">{payrollSummary.totalHours.toFixed(1)}</div>
              </div>
              <div className="summary-card">
                <div className="card-label">Regular Hours</div>
                <div className="card-value">{payrollSummary.totalRegularHours.toFixed(1)}</div>
              </div>
              <div className="summary-card">
                <div className="card-label">Overtime Hours</div>
                <div className="card-value">{payrollSummary.totalOvertimeHours.toFixed(1)}</div>
              </div>
              <div className="summary-card highlight">
                <div className="card-label">Gross Pay</div>
                <div className="card-value">${payrollSummary.totalGrossPay.toFixed(2)}</div>
              </div>
              <div className="summary-card">
                <div className="card-label">Total Deductions</div>
                <div className="card-value">-${payrollSummary.totalDeductions.toFixed(2)}</div>
              </div>
              <div className="summary-card">
                <div className="card-label">Benefits</div>
                <div className="card-value">${payrollSummary.totalBenefits.toFixed(2)}</div>
              </div>
              <div className="summary-card highlight">
                <div className="card-label">Net Pay</div>
                <div className="card-value">${payrollSummary.totalNetPay.toFixed(2)}</div>
              </div>
            </div>
          )}
        </div>

        <div className="payroll-details">
          <div className="details-header">
            <h3>Staff Payroll Details</h3>
            <button 
              className="select-all-button"
              onClick={handleSelectAll}
            >
              {selectedStaff.length === staff.length ? 'Deselect All' : 'Select All'}
            </button>
          </div>

          <div className="payroll-table">
            <table>
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      checked={selectedStaff.length === staff.length}
                      onChange={handleSelectAll}
                    />
                  </th>
                  <th>Employee</th>
                  <th>Role</th>
                  <th>Regular Hrs</th>
                  <th>OT Hrs</th>
                  <th>Holiday Hrs</th>
                  <th>Total Hrs</th>
                  <th>Hourly Rate</th>
                  <th>Gross Pay</th>
                  <th>Deductions</th>
                  <th>Net Pay</th>
                </tr>
              </thead>
              <tbody>
                {payrollData.map(data => (
                  <tr key={data.id} className={selectedStaff.includes(data.id) ? 'selected' : ''}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedStaff.includes(data.id)}
                        onChange={() => handleStaffSelection(data.id)}
                      />
                    </td>
                    <td>{data.name}</td>
                    <td>{data.role}</td>
                    <td>{data.regularHours.toFixed(1)}</td>
                    <td>{data.overtimeHours.toFixed(1)}</td>
                    <td>{data.holidayHours.toFixed(1)}</td>
                    <td className="total-hours">{data.totalHours.toFixed(1)}</td>
                    <td>${data.hourlyRate.toFixed(2)}</td>
                    <td className="gross-pay">${data.grossPay.toFixed(2)}</td>
                    <td className="deductions">-${data.totalDeductions.toFixed(2)}</td>
                    <td className="net-pay">${data.netPay.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="payroll-actions">
          <button 
            className="secondary-button"
            onClick={exportPayrollReport}
          >
            Export Report
          </button>
          <button 
            className="primary-button"
            onClick={handleProcessPayroll}
            disabled={isLoading || payrollData.length === 0}
          >
            {isLoading ? 'Processing...' : 'Process Payroll'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PayrollIntegration;