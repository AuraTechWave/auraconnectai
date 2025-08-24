import React, { useState, useEffect } from 'react';
import websocketService from '../../services/websocket';
import './ConnectionStatus.css';

const ConnectionStatus = () => {
  const [connectionState, setConnectionState] = useState('disconnected');
  const [showBanner, setShowBanner] = useState(false);

  useEffect(() => {
    // Update connection state
    const updateState = () => {
      setConnectionState(websocketService.getConnectionState());
    };

    // Initial state
    updateState();

    // Listen for connection events
    const unsubscribers = [
      websocketService.on('connection:established', () => {
        setConnectionState('connected');
        setShowBanner(false);
      }),
      
      websocketService.on('connection:lost', () => {
        setConnectionState('disconnected');
        setShowBanner(true);
      }),
      
      websocketService.on('connection:reconnecting', (attempt) => {
        setConnectionState('reconnecting');
        console.log(`Reconnection attempt ${attempt}`);
      }),
      
      websocketService.on('connection:failed', () => {
        setConnectionState('failed');
        setShowBanner(true);
      })
    ];

    return () => {
      unsubscribers.forEach(unsub => unsub());
    };
  }, []);

  if (!showBanner || connectionState === 'connected') {
    return null;
  }

  const getStatusMessage = () => {
    switch (connectionState) {
      case 'reconnecting':
        return 'Reconnecting to server...';
      case 'failed':
        return 'Connection lost. Order updates may be delayed.';
      case 'disconnected':
        return 'No internet connection. Working offline.';
      default:
        return 'Connection status unknown';
    }
  };

  const getStatusClass = () => {
    switch (connectionState) {
      case 'reconnecting':
        return 'warning';
      case 'failed':
      case 'disconnected':
        return 'error';
      default:
        return '';
    }
  };

  return (
    <div className={`connection-banner ${getStatusClass()}`}>
      <div className="connection-content">
        <span className="connection-icon">
          {connectionState === 'reconnecting' ? '⟳' : '⚠️'}
        </span>
        <span className="connection-message">{getStatusMessage()}</span>
        {connectionState === 'failed' && (
          <button 
            className="retry-button"
            onClick={() => window.location.reload()}
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
};

export default ConnectionStatus;