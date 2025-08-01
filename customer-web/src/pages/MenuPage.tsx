import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Grid,
  TextField,
  InputAdornment,
  CircularProgress,
  Alert,
} from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import { MenuCategories } from '../components/menu/MenuCategories';
import { MenuItemCard } from '../components/menu/MenuItemCard';
import { MenuItemModal } from '../components/menu/MenuItemModal';
import { MenuItem, MenuItemWithDetails, MenuCategory } from '../types';

export const MenuPage: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedItem, setSelectedItem] = useState<MenuItemWithDetails | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  // Fetch categories
  const {
    data: categories = [],
    isLoading: categoriesLoading,
    error: categoriesError,
  } = useQuery({
    queryKey: ['menu-categories'],
    queryFn: api.getCategories,
  });

  // Fetch menu items
  const {
    data: menuData,
    isLoading: itemsLoading,
    error: itemsError,
  } = useQuery({
    queryKey: ['menu-items', selectedCategory, searchQuery],
    queryFn: () =>
      api.getMenuItems({
        category_id: selectedCategory,
        query: searchQuery,
        limit: 100,
      }),
  });

  const items = menuData?.items || [];

  // Fetch item details when modal opens
  const fetchItemDetails = async (item: MenuItem) => {
    try {
      const details = await api.getMenuItem(item.id);
      setSelectedItem(details);
      setModalOpen(true);
    } catch (error) {
      console.error('Error fetching item details:', error);
    }
  };

  const handleCloseModal = () => {
    setModalOpen(false);
    setSelectedItem(null);
  };

  if (categoriesError || itemsError) {
    return (
      <Container>
        <Alert severity="error" sx={{ mt: 4 }}>
          Error loading menu. Please try again later.
        </Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h3" gutterBottom>
          Our Menu
        </Typography>
        <Typography variant="h6" color="text.secondary" paragraph>
          Explore our delicious offerings
        </Typography>

        {/* Search Bar */}
        <TextField
          fullWidth
          placeholder="Search menu items..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
          sx={{ mb: 4 }}
        />

        {/* Categories */}
        <MenuCategories
          categories={categories}
          selectedCategory={selectedCategory}
          onSelectCategory={setSelectedCategory}
          isLoading={categoriesLoading}
        />

        {/* Menu Items */}
        {itemsLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : items.length === 0 ? (
          <Alert severity="info">
            No items found. Try adjusting your search or category filter.
          </Alert>
        ) : (
          <Grid container spacing={3}>
            {items.map((item) => (
              <Grid item xs={12} sm={6} md={4} lg={3} key={item.id}>
                <MenuItemCard item={item} onViewDetails={fetchItemDetails} />
              </Grid>
            ))}
          </Grid>
        )}
      </Box>

      {/* Item Details Modal */}
      <MenuItemModal
        item={selectedItem}
        open={modalOpen}
        onClose={handleCloseModal}
      />
    </Container>
  );
};