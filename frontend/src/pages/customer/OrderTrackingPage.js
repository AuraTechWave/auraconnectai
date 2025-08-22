import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import useOrderStore from '../../stores/useOrderStore';
import { orderApi } from '../../services/api';
import wsService from '../../services/websocket';
import LoadingSpinner from '../../components/customer/LoadingSpinner';
import ErrorMessage from '../../components/customer/ErrorMessage';
import './OrderTrackingPage.css';

const ORDER_STATUSES = {
  pending: { label: 'Order Placed', icon: '📝', step: 1 },
  confirmed: { label: 'Confirmed', icon: '✅', step: 2 },
  preparing: { label: 'Preparing', icon: '👨‍🍳', step: 3 },
  ready: { label: 'Ready', icon: '🍽️', step: 4 },
  completed: { label: 'Completed', icon: '✨', step: 5 },
  cancelled: { label: 'Cancelled', icon: '❌', step: -1 },
};

function OrderTrackingPage() {
  const { orderId } = useParams();
  const navigate = useNavigate();
  const { currentOrder, updateOrderStatus, wsConnected } = useOrderStore();
  const [orderData, setOrderData] = useState(null);
  const [estimatedTime, setEstimatedTime] = useState(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['order', orderId],
    queryFn: async () => {
      const response = await orderApi.getOrder(orderId);
      return response.data;
    },
    refetchInterval: !wsConnected ? 10000 : false,
  });

  useEffect(() => {
    if (data) {
      setOrderData(data);
      calculateEstimatedTime(data);
    }
  }, [data]);

  useEffect(() => {
    if (currentOrder?.id === parseInt(orderId)) {
      setOrderData(currentOrder);
      calculateEstimatedTime(currentOrder);
    }
  }, [currentOrder, orderId]);

  useEffect(() => {
    wsService.subscribeToOrder(orderId);

    const unsubscribeStatus = wsService.on('order:status', (update) => {
      if (update.orderId === parseInt(orderId)) {
        setOrderData((prev) => ({ ...prev, ...update }));
        updateOrderStatus(update.orderId, update.status, update);
      }
    });

    const unsubscribeUpdate = wsService.on('order:update', (update) => {
      if (update.orderId === parseInt(orderId)) {
        setOrderData((prev) => ({ ...prev, ...update }));
      }
    });

    return () => {
      unsubscribeStatus();
      unsubscribeUpdate();
      wsService.unsubscribeFromOrder(orderId);
    };
  }, [orderId, updateOrderStatus]);

  const calculateEstimatedTime = (order) => {
    if (!order.created_at) return;
    
    const createdTime = new Date(order.created_at);
    let estimatedMinutes = 30;
    
    switch (order.status) {
      case 'pending':
        estimatedMinutes = 30;
        break;
      case 'confirmed':
        estimatedMinutes = 25;
        break;
      case 'preparing':
        estimatedMinutes = 15;
        break;
      case 'ready':
        estimatedMinutes = 0;
        break;
      default:
        estimatedMinutes = 0;
    }
    
    if (estimatedMinutes > 0) {
      const estimatedDate = new Date(createdTime.getTime() + estimatedMinutes * 60000);
      setEstimatedTime(estimatedDate);
    } else {
      setEstimatedTime(null);
    }
  };

  const handleCancelOrder = async () => {
    if (!window.confirm('Are you sure you want to cancel this order?')) {
      return;
    }

    const result = await useOrderStore.getState().cancelOrder(orderId);
    if (result.success) {
      navigate('/orders');
    } else {
      alert(result.error || 'Failed to cancel order');
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading order details..." />;
  }

  if (error) {
    return <ErrorMessage message="Failed to load order details. Please try again." />;
  }

  if (!orderData) {
    return <ErrorMessage message="Order not found." />;
  }

  const currentStatus = ORDER_STATUSES[orderData.status] || ORDER_STATUSES.pending;
  const canCancel = ['pending', 'confirmed'].includes(orderData.status);

  return (
    <div className="order-tracking-page">
      <div className="tracking-header">
        <button className="back-btn" onClick={() => navigate('/orders')}>
          ← Back to Orders
        </button>
        <h1>Order #{orderData.id}</h1>
        {wsConnected && (
          <span className="live-indicator">
            <span className="live-dot"></span> Live Updates
          </span>
        )}
      </div>

      <div className="tracking-content">
        <div className="order-status-section">
          <div className="status-current">
            <span className="status-icon">{currentStatus.icon}</span>
            <h2>{currentStatus.label}</h2>
            {estimatedTime && orderData.status !== 'ready' && (
              <p className="estimated-time">
                Estimated ready by: {estimatedTime.toLocaleTimeString([], { 
                  hour: '2-digit', 
                  minute: '2-digit' 
                })}
              </p>
            )}
          </div>

          {orderData.status !== 'cancelled' && (
            <div className="status-timeline">
              {Object.entries(ORDER_STATUSES)
                .filter(([key]) => key !== 'cancelled')
                .map(([key, status]) => (
                  <div 
                    key={key}
                    className={`timeline-step ${
                      status.step <= currentStatus.step ? 'completed' : ''
                    } ${key === orderData.status ? 'current' : ''}`}
                  >
                    <div className="step-icon">{status.icon}</div>
                    <div className="step-label">{status.label}</div>
                  </div>
                ))}
            </div>
          )}
        </div>

        <div className="order-details-section">
          <h3>Order Details</h3>
          <div className="order-info">
            <div className="info-row">
              <span>Order Type:</span>
              <span>{orderData.order_type || 'Dine In'}</span>
            </div>
            {orderData.table_number && (
              <div className="info-row">
                <span>Table Number:</span>
                <span>{orderData.table_number}</span>
              </div>
            )}
            <div className="info-row">
              <span>Placed At:</span>
              <span>
                {new Date(orderData.created_at).toLocaleString()}
              </span>
            </div>
          </div>

          <div className="order-items">
            <h4>Items</h4>
            {orderData.items?.map((item, index) => (
              <div key={index} className="order-item">
                <div className="item-details">
                  <span className="item-quantity">{item.quantity}x</span>
                  <span className="item-name">{item.name}</span>
                  {item.modifiers?.length > 0 && (
                    <span className="item-modifiers">
                      ({item.modifiers.map(m => m.name).join(', ')})
                    </span>
                  )}
                </div>
                <span className="item-price">
                  ${((item.price || 0) * item.quantity).toFixed(2)}
                </span>
              </div>
            ))}
          </div>

          {orderData.special_instructions && (
            <div className="special-instructions">
              <h4>Special Instructions</h4>
              <p>{orderData.special_instructions}</p>
            </div>
          )}

          <div className="order-summary">
            <div className="summary-line">
              <span>Subtotal:</span>
              <span>${(orderData.subtotal || 0).toFixed(2)}</span>
            </div>
            {orderData.discount > 0 && (
              <div className="summary-line">
                <span>Discount:</span>
                <span>-${orderData.discount.toFixed(2)}</span>
              </div>
            )}
            <div className="summary-line">
              <span>Tax:</span>
              <span>${(orderData.tax || 0).toFixed(2)}</span>
            </div>
            <div className="summary-line total">
              <span>Total:</span>
              <span>${(orderData.total || 0).toFixed(2)}</span>
            </div>
          </div>
        </div>

        {canCancel && (
          <div className="order-actions">
            <button 
              className="cancel-order-btn"
              onClick={handleCancelOrder}
            >
              Cancel Order
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default OrderTrackingPage;