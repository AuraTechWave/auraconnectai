/**
 * Skeleton loader components for better loading UX
 * Provides visual placeholders while content is being fetched
 */

import React from 'react';
import './SkeletonLoader.css';

interface SkeletonProps {
  className?: string;
  width?: string | number;
  height?: string | number;
  variant?: 'text' | 'rectangular' | 'circular';
  animation?: 'pulse' | 'wave' | 'none';
}

export const Skeleton: React.FC<SkeletonProps> = ({
  className = '',
  width = '100%',
  height = '1rem',
  variant = 'text',
  animation = 'pulse'
}) => {
  const style: React.CSSProperties = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
  };

  return (
    <div
      className={`skeleton skeleton--${variant} skeleton--${animation} ${className}`}
      style={style}
      aria-label="Loading content"
    />
  );
};

export const PayrollHistoryTableSkeleton: React.FC = () => {
  return (
    <div className="payroll-history-skeleton">
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
          {Array.from({ length: 5 }).map((_, index) => (
            <tr key={index}>
              <td>
                <Skeleton width="140px" />
              </td>
              <td>
                <Skeleton width="80px" />
              </td>
              <td>
                <Skeleton width="80px" />
              </td>
              <td>
                <Skeleton width="80px" />
              </td>
              <td>
                <Skeleton width="90px" height="24px" variant="rectangular" />
              </td>
              <td>
                <Skeleton width="100px" height="32px" variant="rectangular" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export const PayrollDetailSkeleton: React.FC = () => {
  return (
    <div className="payroll-detail-skeleton">
      <div className="detail-header">
        <Skeleton width="150px" height="24px" />
        <Skeleton width="24px" height="24px" variant="circular" />
      </div>
      
      <div className="detail-content">
        {/* Earnings section */}
        <section>
          <Skeleton width="80px" height="20px" className="section-title" />
          <table>
            <tbody>
              {Array.from({ length: 4 }).map((_, index) => (
                <tr key={index}>
                  <td>
                    <Skeleton width="120px" />
                  </td>
                  <td>
                    <Skeleton width="80px" />
                  </td>
                </tr>
              ))}
              <tr className="total">
                <td>
                  <Skeleton width="80px" />
                </td>
                <td>
                  <Skeleton width="90px" />
                </td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* Deductions section */}
        <section>
          <Skeleton width="90px" height="20px" className="section-title" />
          <table>
            <tbody>
              {Array.from({ length: 5 }).map((_, index) => (
                <tr key={index}>
                  <td>
                    <Skeleton width="110px" />
                  </td>
                  <td>
                    <Skeleton width="80px" />
                  </td>
                </tr>
              ))}
              <tr className="total">
                <td>
                  <Skeleton width="120px" />
                </td>
                <td>
                  <Skeleton width="90px" />
                </td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* Net pay */}
        <div className="net-pay">
          <Skeleton width="70px" height="20px" />
          <div className="amount">
            <Skeleton width="100px" height="32px" />
          </div>
        </div>
      </div>
    </div>
  );
};

export const PayrollCardSkeleton: React.FC = () => {
  return (
    <div className="payroll-card-skeleton">
      <div className="card-header">
        <Skeleton width="120px" height="20px" />
        <Skeleton width="80px" height="32px" variant="rectangular" />
      </div>
      <div className="card-content">
        <div className="metric-row">
          <Skeleton width="60px" height="14px" />
          <Skeleton width="80px" height="18px" />
        </div>
        <div className="metric-row">
          <Skeleton width="70px" height="14px" />
          <Skeleton width="90px" height="18px" />
        </div>
        <div className="metric-row">
          <Skeleton width="55px" height="14px" />
          <Skeleton width="85px" height="18px" />
        </div>
      </div>
    </div>
  );
};

export const PayrollStatsSkeleton: React.FC = () => {
  return (
    <div className="payroll-stats-skeleton">
      <div className="stats-grid">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="stat-card">
            <Skeleton width="80px" height="16px" className="stat-label" />
            <Skeleton width="100px" height="28px" className="stat-value" />
            <Skeleton width="60px" height="14px" className="stat-change" />
          </div>
        ))}
      </div>
    </div>
  );
};