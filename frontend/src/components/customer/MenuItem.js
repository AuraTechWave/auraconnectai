import React, { useState } from 'react';
import './MenuItem.css';

function MenuItem({ item, onAddToCart }) {
  const [quantity, setQuantity] = useState(1);
  const [selectedModifiers, setSelectedModifiers] = useState([]);
  const [showDetails, setShowDetails] = useState(false);

  const handleModifierToggle = (modifier) => {
    setSelectedModifiers((prev) => {
      const exists = prev.find((m) => m.id === modifier.id);
      if (exists) {
        return prev.filter((m) => m.id !== modifier.id);
      }
      return [...prev, modifier];
    });
  };

  const handleAddToCart = () => {
    for (let i = 0; i < quantity; i++) {
      onAddToCart(item, selectedModifiers);
    }
    setQuantity(1);
    setSelectedModifiers([]);
    setShowDetails(false);
  };

  const getTotalPrice = () => {
    const basePrice = item.price || 0;
    const modifiersPrice = selectedModifiers.reduce((sum, mod) => sum + (mod.price || 0), 0);
    return ((basePrice + modifiersPrice) * quantity).toFixed(2);
  };

  return (
    <>
      <div className="menu-item" onClick={() => setShowDetails(true)}>
        {item.image_url && (
          <div className="item-image">
            <img src={item.image_url} alt={item.name} />
          </div>
        )}
        <div className="item-content">
          <h3 className="item-name">{item.name}</h3>
          <p className="item-description">{item.description}</p>
          <div className="item-footer">
            <span className="item-price">${item.price?.toFixed(2)}</span>
            <button 
              className="add-to-cart-btn"
              onClick={(e) => {
                e.stopPropagation();
                if (item.modifiers?.length > 0) {
                  setShowDetails(true);
                } else {
                  onAddToCart(item, []);
                }
              }}
            >
              Add to Cart
            </button>
          </div>
        </div>
      </div>

      {showDetails && (
        <div className="item-modal-overlay" onClick={() => setShowDetails(false)}>
          <div className="item-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowDetails(false)}>
              ×
            </button>
            
            <div className="modal-header">
              {item.image_url && (
                <img src={item.image_url} alt={item.name} className="modal-image" />
              )}
              <h2>{item.name}</h2>
              <p className="modal-description">{item.description}</p>
            </div>

            {item.modifiers?.length > 0 && (
              <div className="modifiers-section">
                <h3>Customize Your Order</h3>
                {item.modifiers.map((modifier) => (
                  <label key={modifier.id} className="modifier-option">
                    <input
                      type="checkbox"
                      checked={selectedModifiers.some((m) => m.id === modifier.id)}
                      onChange={() => handleModifierToggle(modifier)}
                    />
                    <span className="modifier-name">{modifier.name}</span>
                    {modifier.price > 0 && (
                      <span className="modifier-price">+${modifier.price.toFixed(2)}</span>
                    )}
                  </label>
                ))}
              </div>
            )}

            <div className="quantity-section">
              <label>Quantity:</label>
              <div className="quantity-controls">
                <button 
                  onClick={() => setQuantity(Math.max(1, quantity - 1))}
                  disabled={quantity <= 1}
                >
                  -
                </button>
                <span className="quantity-value">{quantity}</span>
                <button onClick={() => setQuantity(quantity + 1)}>
                  +
                </button>
              </div>
            </div>

            {item.nutritional_info && (
              <div className="nutritional-info">
                <h4>Nutritional Information</h4>
                <p>Calories: {item.nutritional_info.calories}</p>
                {item.nutritional_info.allergens && (
                  <p>Allergens: {item.nutritional_info.allergens.join(', ')}</p>
                )}
              </div>
            )}

            <div className="modal-footer">
              <div className="total-price">
                Total: ${getTotalPrice()}
              </div>
              <button className="add-to-cart-btn primary" onClick={handleAddToCart}>
                Add to Cart
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default MenuItem;