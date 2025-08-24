import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useCartStore from '../../stores/useCartStore';
import useCustomerStore from '../../stores/useCustomerStore';
import useOrderStore from '../../stores/useOrderStore';
import { paymentApi } from '../../services/api';
import './CheckoutPage.css';

function CheckoutPage() {
  const navigate = useNavigate();
  const { 
    items, 
    getSubtotal, 
    getTax, 
    getTotal, 
    clearCart,
    orderType,
    tableNumber,
    specialInstructions,
    appliedPromoCode,
    discount
  } = useCartStore();
  
  const { customer, selectedAddress } = useCustomerStore();
  const { createOrder } = useOrderStore();
  
  const [paymentMethod, setPaymentMethod] = useState('card');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState('');

  const handlePlaceOrder = async () => {
    setIsProcessing(true);
    setError('');

    try {
      const orderData = {
        customer_id: customer.id,
        items: items.map(item => ({
          menu_item_id: item.id,
          quantity: item.quantity,
          modifiers: item.modifiers?.map(m => m.id) || [],
          price: item.price,
        })),
        order_type: orderType,
        table_number: tableNumber,
        special_instructions: specialInstructions,
        promo_code: appliedPromoCode,
        discount_amount: discount,
        subtotal: getSubtotal(),
        tax: getTax(),
        total: getTotal(),
        payment_method: paymentMethod,
        delivery_address: orderType === 'delivery' ? selectedAddress : null,
      };

      const result = await createOrder(orderData);
      
      if (result.success) {
        clearCart();
        navigate(`/orders/${result.order.id}`);
      } else {
        setError(result.error || 'Failed to place order');
      }
    } catch (err) {
      setError('An error occurred while placing your order');
    } finally {
      setIsProcessing(false);
    }
  };

  if (items.length === 0) {
    navigate('/cart');
    return null;
  }

  return (
    <div className="checkout-page">
      <h1>Checkout</h1>

      <div className="checkout-content">
        <div className="checkout-main">
          <section className="delivery-info">
            <h2>Delivery Information</h2>
            <div className="info-display">
              <p><strong>Order Type:</strong> {orderType}</p>
              {orderType === 'dine-in' && tableNumber && (
                <p><strong>Table Number:</strong> {tableNumber}</p>
              )}
              {orderType === 'delivery' && selectedAddress && (
                <div className="address-display">
                  <p><strong>Delivery Address:</strong></p>
                  <p>{selectedAddress.street}</p>
                  <p>{selectedAddress.city}, {selectedAddress.state} {selectedAddress.zip}</p>
                </div>
              )}
            </div>
          </section>

          <section className="payment-method">
            <h2>Payment Method</h2>
            <div className="payment-options">
              <label>
                <input
                  type="radio"
                  value="card"
                  checked={paymentMethod === 'card'}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                />
                Credit/Debit Card
              </label>
              <label>
                <input
                  type="radio"
                  value="cash"
                  checked={paymentMethod === 'cash'}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                />
                Cash
              </label>
              <label>
                <input
                  type="radio"
                  value="digital"
                  checked={paymentMethod === 'digital'}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                />
                Digital Wallet
              </label>
            </div>
          </section>

          {specialInstructions && (
            <section className="special-instructions">
              <h3>Special Instructions</h3>
              <p>{specialInstructions}</p>
            </section>
          )}
        </div>

        <div className="checkout-sidebar">
          <div className="order-summary">
            <h2>Order Summary</h2>
            
            <div className="items-list">
              {items.map((item) => (
                <div key={item.cartId} className="summary-item">
                  <span>{item.quantity}x {item.name}</span>
                  <span>${(item.price * item.quantity).toFixed(2)}</span>
                </div>
              ))}
            </div>

            <div className="summary-totals">
              <div className="total-line">
                <span>Subtotal:</span>
                <span>${getSubtotal().toFixed(2)}</span>
              </div>
              {discount > 0 && (
                <div className="total-line discount">
                  <span>Discount:</span>
                  <span>-${discount.toFixed(2)}</span>
                </div>
              )}
              <div className="total-line">
                <span>Tax:</span>
                <span>${getTax().toFixed(2)}</span>
              </div>
              <div className="total-line final">
                <span>Total:</span>
                <span>${getTotal().toFixed(2)}</span>
              </div>
            </div>

            {error && (
              <div className="error-message">
                {error}
              </div>
            )}

            <button
              className="place-order-btn"
              onClick={handlePlaceOrder}
              disabled={isProcessing}
            >
              {isProcessing ? 'Processing...' : 'Place Order'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CheckoutPage;