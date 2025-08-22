import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import useOrderStore from '../../stores/useOrderStore';
import LoadingSpinner from '../../components/customer/LoadingSpinner';
import './OrdersPage.css';

function OrdersPage() {
  const { activeOrders, orderHistory, fetchMyOrders, isLoading } = useOrderStore();

  useEffect(() => {
    fetchMyOrders();
  }, []);

  if (isLoading) {
    return <LoadingSpinner message="Loading your orders..." />;
  }

  const OrderCard = ({ order }) => (
    <Link to={`/orders/${order.id}`} className="order-card">
      <div className="order-header">
        <span className="order-id">Order #{order.id}</span>
        <span className={`order-status ${order.status}`}>
          {order.status.replace('_', ' ')}
        </span>
      </div>
      <div className="order-details">
        <p className="order-date">
          {new Date(order.created_at).toLocaleDateString()} at{' '}
          {new Date(order.created_at).toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
          })}
        </p>
        <p className="order-items">
          {order.items?.length || 0} items • ${(order.total || 0).toFixed(2)}
        </p>
      </div>
    </Link>
  );

  return (
    <div className="orders-page">
      <h1>My Orders</h1>

      {activeOrders.length === 0 && orderHistory.length === 0 ? (
        <div className="no-orders">
          <p>You haven&apos;t placed any orders yet.</p>
          <Link to="/menu" className="browse-menu-btn">
            Browse Menu
          </Link>
        </div>
      ) : (
        <>
          {activeOrders.length > 0 && (
            <section className="active-orders">
              <h2>Active Orders</h2>
              <div className="orders-grid">
                {activeOrders.map((order) => (
                  <OrderCard key={order.id} order={order} />
                ))}
              </div>
            </section>
          )}

          {orderHistory.length > 0 && (
            <section className="order-history">
              <h2>Order History</h2>
              <div className="orders-grid">
                {orderHistory.map((order) => (
                  <OrderCard key={order.id} order={order} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default OrdersPage;