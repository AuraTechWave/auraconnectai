import React, { useEffect } from 'react';
import { secureExportService } from '../../../../services/secureExportService';

interface PDFExporterProps {
  data: any;
  onExport: (result: any) => void;
  onError: (error: Error) => void;
}

const PDFExporter: React.FC<PDFExporterProps> = ({ data, onExport, onError }) => {
  useEffect(() => {
    const exportPDF = async () => {
      try {
        // Dynamically import jsPDF only when needed
        const { default: jsPDF } = await import(
          /* webpackChunkName: "jspdf" */ 'jspdf'
        );
        const { default: autoTable } = await import(
          /* webpackChunkName: "jspdf-autotable" */ 'jspdf-autotable'
        );

        const doc = new jsPDF();
        
        // Add title
        doc.setFontSize(18);
        doc.text('Schedule Export', 14, 22);
        
        // Add date
        doc.setFontSize(11);
        doc.text(`Generated: ${new Date().toLocaleString()}`, 14, 32);

        // Prepare table data
        const tableData = data.shifts.map((shift: any) => [
          shift.staff_name,
          shift.date,
          shift.start_time,
          shift.end_time,
          shift.hours,
          shift.role,
        ]);

        // Add table
        (doc as any).autoTable({
          head: [['Staff', 'Date', 'Start', 'End', 'Hours', 'Role']],
          body: tableData,
          startY: 40,
          theme: 'grid',
          styles: {
            fontSize: 10,
            cellPadding: 3,
          },
          headStyles: {
            fillColor: [66, 139, 202],
            textColor: 255,
            fontStyle: 'bold',
          },
        });

        // Generate blob
        const pdfBlob = doc.output('blob');
        
        // Upload to server for secure storage and get signed URL
        const exportResult = await secureExportService.requestExport(
          'schedule',
          data.scheduleId,
          {
            format: 'pdf',
            redactPII: false, // Schedule data typically doesn't need PII redaction
          }
        );

        onExport({
          blob: pdfBlob,
          filename: `schedule-${Date.now()}.pdf`,
          exportResult,
        });
      } catch (error) {
        onError(error as Error);
      }
    };

    exportPDF();
  }, [data, onExport, onError]);

  return <div>Generating PDF...</div>;
};

export default PDFExporter;