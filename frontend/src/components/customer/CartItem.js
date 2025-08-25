import React from 'react';
import useCartStore from '../../stores/useCartStore';
import './CartItem.css';

function CartItem({ item }) {
  const { updateItemQuantity, removeItem } = useCartStore();

  const handleQuantityChange = (newQuantity) => {
    updateItemQuantity(item.cartId, newQuantity);
  };

  const itemTotal = (item.price + (item.modifiers?.reduce((sum, mod) => sum + mod.price, 0) || 0)) * item.quantity;

  return (
    <div className="cart-item">
      <div className="item-info">
        <h4>{item.name}</h4>
        {item.modifiers?.length > 0 && (
          <p className="item-modifiers">
            {item.modifiers.map(m => m.name).join(', ')}
          </p>
        )}
      </div>
      
      <div className="item-controls">
        <div className="quantity-controls">
          <button 
            onClick={() => handleQuantityChange(item.quantity - 1)}
            disabled={item.quantity <= 1}
          >
            -
          </button>
          <span>{item.quantity}</span>
          <button onClick={() => handleQuantityChange(item.quantity + 1)}>
            +
          </button>
        </div>
        
        <div className="item-price">
          ${itemTotal.toFixed(2)}
        </div>
        
        <button 
          className="remove-btn"
          onClick={() => removeItem(item.cartId)}
          title="Remove item"
        >
          ×
        </button>
      </div>
    </div>
  );
}

export default CartItem;