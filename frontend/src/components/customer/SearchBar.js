import React, { useState, useEffect } from 'react';
import './SearchBar.css';

function SearchBar({ value, onChange, placeholder = 'Search...' }) {
  const [localValue, setLocalValue] = useState(value || '');

  useEffect(() => {
    const debounceTimer = setTimeout(() => {
      onChange(localValue);
    }, 300);

    return () => clearTimeout(debounceTimer);
  }, [localValue, onChange]);

  return (
    <div className="search-bar">
      <input
        type="text"
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        placeholder={placeholder}
        className="search-input"
      />
      {localValue && (
        <button 
          className="clear-btn"
          onClick={() => {
            setLocalValue('');
            onChange('');
          }}
        >
          ×
        </button>
      )}
    </div>
  );
}

export default SearchBar;