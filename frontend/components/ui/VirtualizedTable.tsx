import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import './VirtualizedTable.css';

interface Column<T> {
  key: string;
  title: string;
  width?: number;
  minWidth?: number;
  render?: (value: any, record: T, index: number) => React.ReactNode;
  align?: 'left' | 'center' | 'right';
  fixed?: 'left' | 'right';
  sortable?: boolean;
}

interface VirtualizedTableProps<T> {
  data: T[];
  columns: Column<T>[];
  rowHeight?: number;
  height?: number;
  overscan?: number;
  loading?: boolean;
  emptyText?: string;
  className?: string;
  onRowClick?: (record: T, index: number) => void;
  rowClassName?: (record: T, index: number) => string;
  sticky?: boolean;
}

const VirtualizedTable = <T extends Record<string, any>>({
  data,
  columns,
  rowHeight = 48,
  height = 400,
  overscan = 5,
  loading = false,
  emptyText = 'No data',
  className = '',
  onRowClick,
  rowClassName,
  sticky = true,
}: VirtualizedTableProps<T>) => {
  const [scrollTop, setScrollTop] = useState(0);
  const [containerHeight, setContainerHeight] = useState(height);
  const scrollElementRef = useRef<HTMLDivElement>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  // Calculate visible range
  const visibleRange = useMemo(() => {
    const containerHeight = height;
    const startIndex = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
    const endIndex = Math.min(
      data.length - 1,
      Math.ceil((scrollTop + containerHeight) / rowHeight) + overscan
    );
    return { startIndex, endIndex };
  }, [scrollTop, height, rowHeight, overscan, data.length]);

  // Calculate total height and visible items
  const totalHeight = data.length * rowHeight;
  const visibleItems = useMemo(() => {
    return data.slice(visibleRange.startIndex, visibleRange.endIndex + 1);
  }, [data, visibleRange]);

  // Handle scroll
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const scrollTop = e.currentTarget.scrollTop;
    setScrollTop(scrollTop);
  }, []);

  // Setup resize observer for responsive height
  useEffect(() => {
    if (!scrollElementRef.current) return;

    resizeObserverRef.current = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerHeight(entry.contentRect.height);
      }
    });

    resizeObserverRef.current.observe(scrollElementRef.current);

    return () => {
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
      }
    };
  }, []);

  // Calculate column widths and positions
  const { columnWidths, totalWidth } = useMemo(() => {
    const containerWidth = scrollElementRef.current?.clientWidth || 1000;
    let totalFixedWidth = 0;
    let flexColumns = 0;

    // Calculate fixed widths first
    columns.forEach(col => {
      if (col.width) {
        totalFixedWidth += col.width;
      } else {
        flexColumns++;
      }
    });

    const remainingWidth = Math.max(0, containerWidth - totalFixedWidth);
    const flexWidth = flexColumns > 0 ? remainingWidth / flexColumns : 0;

    const widths = columns.map(col => {
      if (col.width) return col.width;
      return Math.max(col.minWidth || 100, flexWidth);
    });

    return {
      columnWidths: widths,
      totalWidth: Math.max(containerWidth, widths.reduce((sum, w) => sum + w, 0))
    };
  }, [columns, scrollElementRef.current?.clientWidth]);

  // Render table header
  const renderHeader = () => (
    <div 
      className={`virtualized-table-header ${sticky ? 'sticky' : ''}`}
      style={{ width: totalWidth }}
    >
      {columns.map((column, index) => (
        <div
          key={column.key}
          className={`virtualized-table-header-cell ${column.align || 'left'}`}
          style={{ 
            width: columnWidths[index],
            minWidth: columnWidths[index]
          }}
        >
          {column.title}
        </div>
      ))}
    </div>
  );

  // Render table row
  const renderRow = (record: T, index: number, actualIndex: number) => {
    const rowClass = [
      'virtualized-table-row',
      index % 2 === 0 ? 'even' : 'odd',
      rowClassName ? rowClassName(record, actualIndex) : '',
    ].filter(Boolean).join(' ');

    return (
      <div
        key={actualIndex}
        className={rowClass}
        style={{
          height: rowHeight,
          width: totalWidth,
          transform: `translateY(${(visibleRange.startIndex + index) * rowHeight}px)`,
        }}
        onClick={onRowClick ? () => onRowClick(record, actualIndex) : undefined}
      >
        {columns.map((column, colIndex) => {
          const value = record[column.key];
          const content = column.render 
            ? column.render(value, record, actualIndex)
            : value;

          return (
            <div
              key={column.key}
              className={`virtualized-table-cell ${column.align || 'left'}`}
              style={{
                width: columnWidths[colIndex],
                minWidth: columnWidths[colIndex]
              }}
            >
              {content}
            </div>
          );
        })}
      </div>
    );
  };

  if (loading) {
    return (
      <div className={`virtualized-table-container ${className}`} style={{ height }}>
        <div className="virtualized-table-loading">
          <div className="loading-spinner">
            <div className="spinner"></div>
          </div>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className={`virtualized-table-container ${className}`} style={{ height }}>
        <div className="virtualized-table-empty">
          <div className="empty-icon">📋</div>
          <p>{emptyText}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`virtualized-table-container ${className}`} style={{ height }}>
      {renderHeader()}
      
      <div
        ref={scrollElementRef}
        className="virtualized-table-body"
        style={{ height: height - (sticky ? 48 : 0), overflowY: 'auto', overflowX: 'auto' }}
        onScroll={handleScroll}
      >
        <div
          className="virtualized-table-virtual-list"
          style={{ height: totalHeight, position: 'relative', width: totalWidth }}
        >
          {visibleItems.map((record, index) => 
            renderRow(record, index, visibleRange.startIndex + index)
          )}
        </div>
      </div>
    </div>
  );
};

export default VirtualizedTable;