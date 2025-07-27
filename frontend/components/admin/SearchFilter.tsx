import React from 'react';
import './SearchFilter.css';

interface SearchFilterProps {
  searchTerm: string;
  onSearchChange: (value: string) => void;
  filterStatus?: 'all' | 'active' | 'inactive';
  onFilterChange?: (value: 'all' | 'active' | 'inactive') => void;
  placeholder?: string;
}

const SearchFilter: React.FC<SearchFilterProps> = ({
  searchTerm,
  onSearchChange,
  filterStatus = 'all',
  onFilterChange,
  placeholder = 'Search...'
}) => {
  return (
    <div className="search-filter">
      <div className="search-input-wrapper">
        <i className="icon-search"></i>
        <input
          type="text"
          className="search-input"
          placeholder={placeholder}
          value={searchTerm}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>
      
      {onFilterChange && (
        <div className="filter-buttons">
          <button
            className={`filter-btn ${filterStatus === 'all' ? 'active' : ''}`}
            onClick={() => onFilterChange('all')}
          >
            All
          </button>
          <button
            className={`filter-btn ${filterStatus === 'active' ? 'active' : ''}`}
            onClick={() => onFilterChange('active')}
          >
            Active
          </button>
          <button
            className={`filter-btn ${filterStatus === 'inactive' ? 'active' : ''}`}
            onClick={() => onFilterChange('inactive')}
          >
            Inactive
          </button>
        </div>
      )}
    </div>
  );
};

export default SearchFilter;