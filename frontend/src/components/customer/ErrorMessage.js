import React from 'react';
import './ErrorMessage.css';

function ErrorMessage({ message, onRetry, type = 'error' }) {
  return (
    <div className={`error-message ${type}`}>
      <div className="error-icon">
        {type === 'error' && '⚠️'}
        {type === 'warning' && '⚡'}
        {type === 'info' && 'ℹ️'}
      </div>
      <p className="error-text">{message}</p>
      {onRetry && (
        <button className="retry-btn" onClick={onRetry}>
          Try Again
        </button>
      )}
    </div>
  );
}

export default ErrorMessage;