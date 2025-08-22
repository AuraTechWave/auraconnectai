import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { menuApi } from '../../services/api';
import useCartStore from '../../stores/useCartStore';
import MenuCategory from '../../components/customer/MenuCategory';
import MenuItem from '../../components/customer/MenuItem';
import SearchBar from '../../components/customer/SearchBar';
import LoadingSpinner from '../../components/customer/LoadingSpinner';
import ErrorMessage from '../../components/customer/ErrorMessage';
import './MenuPage.css';

function MenuPage() {
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredItems, setFilteredItems] = useState([]);
  
  const { addItem, getItemCount } = useCartStore();

  const { data: categories, isLoading: categoriesLoading, error: categoriesError } = useQuery({
    queryKey: ['menu-categories'],
    queryFn: async () => {
      const response = await menuApi.getCategories();
      return response.data;
    },
  });

  const { data: categoryItems, isLoading: itemsLoading, error: itemsError } = useQuery({
    queryKey: ['menu-items', selectedCategory],
    queryFn: async () => {
      if (!selectedCategory) {
        const response = await menuApi.getMenuItems({ active_only: true });
        return response.data;
      }
      const response = await menuApi.getCategoryItems(selectedCategory);
      return response.data.items || [];
    },
    enabled: true,
  });

  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ['menu-search', searchQuery],
    queryFn: async () => {
      if (!searchQuery) return [];
      const response = await menuApi.searchMenu(searchQuery);
      return response.data;
    },
    enabled: searchQuery.length > 2,
  });

  useEffect(() => {
    if (searchQuery && searchResults) {
      setFilteredItems(searchResults);
    } else if (categoryItems) {
      setFilteredItems(categoryItems);
    } else {
      setFilteredItems([]);
    }
  }, [searchQuery, searchResults, categoryItems]);

  const handleAddToCart = (item, modifiers = []) => {
    addItem({
      id: item.id,
      name: item.name,
      price: item.price,
      description: item.description,
      image: item.image_url,
      modifiers,
    });
  };

  if (categoriesLoading) {
    return <LoadingSpinner message="Loading menu..." />;
  }

  if (categoriesError) {
    return <ErrorMessage message="Failed to load menu categories. Please try again." />;
  }

  return (
    <div className="menu-page">
      <div className="menu-header">
        <h1>Our Menu</h1>
        <SearchBar 
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Search menu items..."
        />
      </div>

      <div className="menu-content">
        <div className="categories-sidebar">
          <h3>Categories</h3>
          <button
            className={`category-button ${!selectedCategory ? 'active' : ''}`}
            onClick={() => setSelectedCategory(null)}
          >
            All Items
          </button>
          {categories?.map((category) => (
            <MenuCategory
              key={category.id}
              category={category}
              isSelected={selectedCategory === category.id}
              onClick={() => setSelectedCategory(category.id)}
            />
          ))}
        </div>

        <div className="menu-items">
          {itemsLoading || searchLoading ? (
            <LoadingSpinner />
          ) : itemsError ? (
            <ErrorMessage message="Failed to load menu items. Please try again." />
          ) : filteredItems.length === 0 ? (
            <div className="no-items">
              {searchQuery 
                ? `No items found for "${searchQuery}"`
                : 'No items available in this category'}
            </div>
          ) : (
            <div className="items-grid">
              {filteredItems.map((item) => (
                <MenuItem
                  key={item.id}
                  item={item}
                  onAddToCart={handleAddToCart}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {getItemCount() > 0 && (
        <div className="cart-float">
          <a href="/cart" className="cart-float-link">
            <span className="cart-icon">🛒</span>
            <span className="cart-count">{getItemCount()}</span>
            <span className="cart-text">View Cart</span>
          </a>
        </div>
      )}
    </div>
  );
}

export default MenuPage;