import React from 'react';
import { format, parseISO } from 'date-fns';
import jsPDF from 'jspdf';
import 'jspdf-autotable';
import * as XLSX from 'xlsx';

class ScheduleExporter {
  static exportToPDF(shifts, staff, startDate, endDate) {
    const doc = new jsPDF('landscape');
    
    // Add header
    doc.setFontSize(18);
    doc.text('Staff Schedule', 14, 20);
    
    doc.setFontSize(12);
    doc.text(`${format(startDate, 'MMM d, yyyy')} - ${format(endDate, 'MMM d, yyyy')}`, 14, 30);
    
    doc.setFontSize(10);
    doc.text(`Generated on: ${format(new Date(), 'MMM d, yyyy HH:mm')}`, 14, 38);
    
    // Prepare data for table
    const tableData = [];
    const headers = ['Staff Member', 'Role'];
    
    // Add date columns
    let currentDate = new Date(startDate);
    while (currentDate <= endDate) {
      headers.push(format(currentDate, 'EEE MMM d'));
      currentDate.setDate(currentDate.getDate() + 1);
    }
    
    // Build rows for each staff member
    staff.forEach(member => {
      const row = [member.name, member.role];
      
      currentDate = new Date(startDate);
      while (currentDate <= endDate) {
        const dayShifts = shifts.filter(shift => {
          const shiftDate = parseISO(shift.date);
          return shift.staff_id === member.id && 
                 format(shiftDate, 'yyyy-MM-dd') === format(currentDate, 'yyyy-MM-dd');
        });
        
        if (dayShifts.length > 0) {
          const shiftText = dayShifts.map(shift => {
            const start = format(parseISO(shift.start_time), 'HH:mm');
            const end = format(parseISO(shift.end_time), 'HH:mm');
            return `${start}-${end}`;
          }).join('\n');
          row.push(shiftText);
        } else {
          row.push('Off');
        }
        
        currentDate.setDate(currentDate.getDate() + 1);
      }
      
      tableData.push(row);
    });
    
    // Add table
    doc.autoTable({
      head: [headers],
      body: tableData,
      startY: 45,
      styles: {
        fontSize: 8,
        cellPadding: 2
      },
      headStyles: {
        fillColor: [33, 150, 243],
        textColor: 255,
        fontStyle: 'bold'
      },
      alternateRowStyles: {
        fillColor: [245, 245, 245]
      },
      columnStyles: {
        0: { cellWidth: 30 },
        1: { cellWidth: 25 }
      }
    });
    
    // Add summary
    const totalShifts = shifts.length;
    const totalHours = shifts.reduce((sum, shift) => {
      const start = parseISO(shift.start_time);
      const end = parseISO(shift.end_time);
      return sum + (end - start) / (1000 * 60 * 60);
    }, 0);
    
    const finalY = doc.lastAutoTable.finalY + 10;
    doc.setFontSize(10);
    doc.text(`Total Shifts: ${totalShifts}`, 14, finalY);
    doc.text(`Total Hours: ${totalHours.toFixed(1)}`, 14, finalY + 6);
    
    // Save PDF
    doc.save(`schedule-${format(startDate, 'yyyy-MM-dd')}.pdf`);
  }

  static exportToExcel(shifts, staff, startDate, endDate) {
    const wb = XLSX.utils.book_new();
    
    // Schedule Sheet
    const scheduleData = [];
    const headers = ['Staff ID', 'Staff Name', 'Role', 'Date', 'Day', 'Start Time', 'End Time', 'Hours', 'Shift Type', 'Status'];
    scheduleData.push(headers);
    
    shifts.forEach(shift => {
      const staffMember = staff.find(s => s.id === shift.staff_id);
      const shiftDate = parseISO(shift.date);
      const startTime = parseISO(shift.start_time);
      const endTime = parseISO(shift.end_time);
      const hours = (endTime - startTime) / (1000 * 60 * 60);
      
      scheduleData.push([
        shift.staff_id,
        staffMember?.name || 'Unknown',
        staffMember?.role || 'Unknown',
        format(shiftDate, 'yyyy-MM-dd'),
        format(shiftDate, 'EEEE'),
        format(startTime, 'HH:mm'),
        format(endTime, 'HH:mm'),
        hours.toFixed(2),
        shift.shift_type,
        shift.status
      ]);
    });
    
    const scheduleSheet = XLSX.utils.aoa_to_sheet(scheduleData);
    XLSX.utils.book_append_sheet(wb, scheduleSheet, 'Schedule');
    
    // Summary Sheet
    const summaryData = [];
    summaryData.push(['Staff Summary Report']);
    summaryData.push([`Period: ${format(startDate, 'MMM d, yyyy')} - ${format(endDate, 'MMM d, yyyy')}`]);
    summaryData.push([]);
    summaryData.push(['Staff Name', 'Total Shifts', 'Total Hours', 'Regular Hours', 'Overtime Hours']);
    
    staff.forEach(member => {
      const staffShifts = shifts.filter(s => s.staff_id === member.id);
      const totalHours = staffShifts.reduce((sum, shift) => {
        const start = parseISO(shift.start_time);
        const end = parseISO(shift.end_time);
        return sum + (end - start) / (1000 * 60 * 60);
      }, 0);
      
      const regularHours = staffShifts
        .filter(s => s.shift_type === 'REGULAR')
        .reduce((sum, shift) => {
          const start = parseISO(shift.start_time);
          const end = parseISO(shift.end_time);
          return sum + (end - start) / (1000 * 60 * 60);
        }, 0);
      
      const overtimeHours = staffShifts
        .filter(s => s.shift_type === 'OVERTIME')
        .reduce((sum, shift) => {
          const start = parseISO(shift.start_time);
          const end = parseISO(shift.end_time);
          return sum + (end - start) / (1000 * 60 * 60);
        }, 0);
      
      summaryData.push([
        member.name,
        staffShifts.length,
        totalHours.toFixed(2),
        regularHours.toFixed(2),
        overtimeHours.toFixed(2)
      ]);
    });
    
    const summarySheet = XLSX.utils.aoa_to_sheet(summaryData);
    XLSX.utils.book_append_sheet(wb, summarySheet, 'Summary');
    
    // Save Excel file
    XLSX.writeFile(wb, `schedule-${format(startDate, 'yyyy-MM-dd')}.xlsx`);
  }

  static exportToCSV(shifts, staff, startDate, endDate) {
    const csvData = [];
    
    // Headers
    csvData.push([
      'Staff ID',
      'Staff Name',
      'Role',
      'Date',
      'Day',
      'Start Time',
      'End Time',
      'Hours',
      'Shift Type',
      'Status',
      'Hourly Rate',
      'Estimated Cost'
    ]);
    
    // Data rows
    shifts.forEach(shift => {
      const staffMember = staff.find(s => s.id === shift.staff_id);
      const shiftDate = parseISO(shift.date);
      const startTime = parseISO(shift.start_time);
      const endTime = parseISO(shift.end_time);
      const hours = (endTime - startTime) / (1000 * 60 * 60);
      
      csvData.push([
        shift.staff_id,
        staffMember?.name || 'Unknown',
        staffMember?.role || 'Unknown',
        format(shiftDate, 'yyyy-MM-dd'),
        format(shiftDate, 'EEEE'),
        format(startTime, 'HH:mm'),
        format(endTime, 'HH:mm'),
        hours.toFixed(2),
        shift.shift_type,
        shift.status,
        shift.hourly_rate || '',
        shift.estimated_cost || ''
      ]);
    });
    
    // Convert to CSV string
    const csvContent = csvData.map(row => 
      row.map(cell => {
        // Escape quotes and wrap in quotes if contains comma
        const cellStr = String(cell);
        if (cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')) {
          return `"${cellStr.replace(/"/g, '""')}"`;
        }
        return cellStr;
      }).join(',')
    ).join('\n');
    
    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `schedule-${format(startDate, 'yyyy-MM-dd')}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  static prepareForPrint(startDate, endDate) {
    // Add print header
    const printHeader = document.createElement('div');
    printHeader.className = 'print-header';
    printHeader.innerHTML = `
      <h1>Staff Schedule</h1>
      <div class="date-range">${format(startDate, 'MMMM d, yyyy')} - ${format(endDate, 'MMMM d, yyyy')}</div>
      <div class="print-date">Printed on: ${format(new Date(), 'MMMM d, yyyy HH:mm')}</div>
    `;
    
    // Add print footer
    const printFooter = document.createElement('div');
    printFooter.className = 'print-footer';
    printFooter.innerHTML = `
      <div>This schedule is confidential and for internal use only.</div>
      <div>Page <span class="page-number"></span></div>
    `;
    
    // Insert elements
    const scheduleElement = document.querySelector('.schedule-calendar');
    if (scheduleElement) {
      scheduleElement.insertBefore(printHeader, scheduleElement.firstChild);
      scheduleElement.appendChild(printFooter);
    }
    
    // Load print styles
    const printStyles = document.createElement('link');
    printStyles.rel = 'stylesheet';
    printStyles.href = './SchedulePrint.css';
    document.head.appendChild(printStyles);
    
    // Print
    window.print();
    
    // Clean up after printing
    setTimeout(() => {
      printHeader.remove();
      printFooter.remove();
      printStyles.remove();
    }, 1000);
  }
}

export default ScheduleExporter;