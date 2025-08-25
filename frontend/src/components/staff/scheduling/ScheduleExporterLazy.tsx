import React, { lazy, Suspense } from 'react';
import LoadingSpinner from '../../customer/LoadingSpinner';

// Lazy load heavy export libraries
const PDFExporter = lazy(() => 
  import(/* webpackChunkName: "pdf-exporter" */ './exporters/PDFExporter')
);

const ExcelExporter = lazy(() => 
  import(/* webpackChunkName: "excel-exporter" */ './exporters/ExcelExporter')
);

const CSVExporter = lazy(() => 
  import(/* webpackChunkName: "csv-exporter" */ './exporters/CSVExporter')
);

interface ScheduleExporterProps {
  format: 'pdf' | 'excel' | 'csv';
  data: any;
  onExport: (result: any) => void;
  onError: (error: Error) => void;
}

export const ScheduleExporterLazy: React.FC<ScheduleExporterProps> = ({
  format,
  data,
  onExport,
  onError,
}) => {
  const renderExporter = () => {
    switch (format) {
      case 'pdf':
        return (
          <Suspense fallback={<LoadingSpinner message="Loading PDF exporter..." />}>
            <PDFExporter data={data} onExport={onExport} onError={onError} />
          </Suspense>
        );
      
      case 'excel':
        return (
          <Suspense fallback={<LoadingSpinner message="Loading Excel exporter..." />}>
            <ExcelExporter data={data} onExport={onExport} onError={onError} />
          </Suspense>
        );
      
      case 'csv':
        return (
          <Suspense fallback={<LoadingSpinner message="Loading CSV exporter..." />}>
            <CSVExporter data={data} onExport={onExport} onError={onError} />
          </Suspense>
        );
      
      default:
        return null;
    }
  };

  return <>{renderExporter()}</>;
};

export default ScheduleExporterLazy;