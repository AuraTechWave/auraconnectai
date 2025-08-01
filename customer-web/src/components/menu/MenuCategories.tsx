import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Skeleton,
  Chip,
} from '@mui/material';
import { Grid2 as Grid } from '../common/Grid2';
import { MenuCategory } from '../../types';

interface MenuCategoriesProps {
  categories: MenuCategory[];
  selectedCategory: number | null;
  onSelectCategory: (categoryId: number | null) => void;
  isLoading?: boolean;
}

export const MenuCategories: React.FC<MenuCategoriesProps> = ({
  categories,
  selectedCategory,
  onSelectCategory,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <Box sx={{ mb: 4 }}>
        <Grid container spacing={2}>
          {[1, 2, 3, 4].map((i) => (
            <Grid item xs={6} sm={3} key={i}>
              <Skeleton variant="rectangular" height={80} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  return (
    <Box sx={{ mb: 4 }}>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <Chip
          label="All Categories"
          onClick={() => onSelectCategory(null)}
          color={selectedCategory === null ? 'primary' : 'default'}
          variant={selectedCategory === null ? 'filled' : 'outlined'}
        />
        {categories.map((category) => (
          <Chip
            key={category.id}
            label={category.name}
            onClick={() => onSelectCategory(category.id)}
            color={selectedCategory === category.id ? 'primary' : 'default'}
            variant={selectedCategory === category.id ? 'filled' : 'outlined'}
          />
        ))}
      </Box>
    </Box>
  );
};