import React from 'react';
import './MenuCategory.css';

function MenuCategory({ category, isSelected, onClick }) {
  return (
    <button
      className={`category-button ${isSelected ? 'active' : ''}`}
      onClick={onClick}
    >
      <span className="category-name">{category.name}</span>
      {category.item_count > 0 && (
        <span className="item-count">({category.item_count})</span>
      )}
    </button>
  );
}

export default MenuCategory;