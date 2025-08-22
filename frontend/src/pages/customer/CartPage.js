import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useCartStore from '../../stores/useCartStore';
import useCustomerStore from '../../stores/useCustomerStore';
import { promotionsApi } from '../../services/api';
import CartItem from '../../components/customer/CartItem';
import './CartPage.css';

function CartPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useCustomerStore();
  const {
    items,
    getSubtotal,
    getTax,
    getTotal,
    clearCart,
    setOrderType,
    orderType,
    setTableNumber,
    tableNumber,
    setSpecialInstructions,
    specialInstructions,
    appliedPromoCode,
    applyPromoCode,
    removePromoCode,
    discount,
  } = useCartStore();

  const [promoCode, setPromoCode] = useState('');
  const [promoError, setPromoError] = useState('');
  const [isApplyingPromo, setIsApplyingPromo] = useState(false);

  const handleApplyPromo = async () => {
    if (!promoCode.trim()) return;
    
    setIsApplyingPromo(true);
    setPromoError('');
    
    try {
      const response = await promotionsApi.validatePromoCode(promoCode);
      if (response.data.valid) {
        applyPromoCode(promoCode, response.data.discount_amount);
      } else {
        setPromoError('Invalid promo code');
      }
    } catch (error) {
      setPromoError(error.response?.data?.message || 'Failed to apply promo code');
    } finally {
      setIsApplyingPromo(false);
    }
  };

  const handleCheckout = () => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: '/checkout' } });
    } else {
      navigate('/checkout');
    }
  };

  if (items.length === 0) {
    return (
      <div className="cart-page empty">
        <div className="empty-cart">
          <h2>Your Cart is Empty</h2>
          <p>Add some delicious items from our menu!</p>
          <button 
            className="browse-menu-btn"
            onClick={() => navigate('/menu')}
          >
            Browse Menu
          </button>
        </div>
      </div>
    );
  }

  const subtotal = getSubtotal();
  const tax = getTax();
  const total = getTotal();

  return (
    <div className="cart-page">
      <h1>Your Cart</h1>

      <div className="cart-content">
        <div className="cart-items-section">
          <div className="order-type-selector">
            <h3>Order Type</h3>
            <div className="order-type-buttons">
              <button
                className={orderType === 'dine-in' ? 'active' : ''}
                onClick={() => setOrderType('dine-in')}
              >
                Dine In
              </button>
              <button
                className={orderType === 'takeout' ? 'active' : ''}
                onClick={() => setOrderType('takeout')}
              >
                Takeout
              </button>
              <button
                className={orderType === 'delivery' ? 'active' : ''}
                onClick={() => setOrderType('delivery')}
              >
                Delivery
              </button>
            </div>
          </div>

          {orderType === 'dine-in' && (
            <div className="table-number-input">
              <label>Table Number:</label>
              <input
                type="text"
                value={tableNumber || ''}
                onChange={(e) => setTableNumber(e.target.value)}
                placeholder="Enter your table number"
              />
            </div>
          )}

          <div className="cart-items">
            <h3>Items</h3>
            {items.map((item) => (
              <CartItem key={item.cartId} item={item} />
            ))}
          </div>

          <div className="special-instructions">
            <label>Special Instructions:</label>
            <textarea
              value={specialInstructions}
              onChange={(e) => setSpecialInstructions(e.target.value)}
              placeholder="Any special requests or dietary requirements?"
              rows={3}
            />
          </div>
        </div>

        <div className="cart-summary">
          <h3>Order Summary</h3>
          
          <div className="promo-code-section">
            {!appliedPromoCode ? (
              <>
                <input
                  type="text"
                  value={promoCode}
                  onChange={(e) => setPromoCode(e.target.value)}
                  placeholder="Enter promo code"
                  disabled={isApplyingPromo}
                />
                <button 
                  onClick={handleApplyPromo}
                  disabled={isApplyingPromo || !promoCode.trim()}
                >
                  {isApplyingPromo ? 'Applying...' : 'Apply'}
                </button>
                {promoError && <p className="promo-error">{promoError}</p>}
              </>
            ) : (
              <div className="applied-promo">
                <span>Promo: {appliedPromoCode}</span>
                <button onClick={removePromoCode}>Remove</button>
              </div>
            )}
          </div>

          <div className="summary-lines">
            <div className="summary-line">
              <span>Subtotal:</span>
              <span>${subtotal.toFixed(2)}</span>
            </div>
            {discount > 0 && (
              <div className="summary-line discount">
                <span>Discount:</span>
                <span>-${discount.toFixed(2)}</span>
              </div>
            )}
            <div className="summary-line">
              <span>Tax:</span>
              <span>${tax.toFixed(2)}</span>
            </div>
            <div className="summary-line total">
              <span>Total:</span>
              <span>${total.toFixed(2)}</span>
            </div>
          </div>

          <button 
            className="checkout-btn"
            onClick={handleCheckout}
          >
            Proceed to Checkout
          </button>

          <button 
            className="clear-cart-btn"
            onClick={() => {
              if (window.confirm('Are you sure you want to clear your cart?')) {
                clearCart();
              }
            }}
          >
            Clear Cart
          </button>
        </div>
      </div>
    </div>
  );
}

export default CartPage;