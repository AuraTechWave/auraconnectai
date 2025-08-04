import React from 'react';
import {
  Card,
  CardMedia,
  CardContent,
  CardActions,
  Typography,
  Button,
  Chip,
  Box,
  IconButton,
  Stack,
} from '@mui/material';
import {
  Add as AddIcon,
  Remove as RemoveIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { MenuItem } from '../../types';
import { useCartStore } from '../../store/cartStore';

interface MenuItemCardProps {
  item: MenuItem;
  onViewDetails: (item: MenuItem) => void;
}

export const MenuItemCard: React.FC<MenuItemCardProps> = ({ item, onViewDetails }) => {
  const { addItem, getItem, updateItemQuantity } = useCartStore();
  const cartItem = getItem(item.id);
  const quantity = cartItem?.quantity || 0;

  const handleAddToCart = () => {
    addItem(item, 1);
  };

  const handleIncrement = () => {
    updateItemQuantity(item.id, quantity + 1);
  };

  const handleDecrement = () => {
    updateItemQuantity(item.id, quantity - 1);
  };

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {item.image_url && (
        <CardMedia
          component="img"
          height="200"
          image={item.image_url}
          alt={item.name}
          sx={{ objectFit: 'cover' }}
        />
      )}
      <CardContent sx={{ flexGrow: 1 }}>
        <Typography gutterBottom variant="h6" component="h2">
          {item.name}
        </Typography>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            mb: 2,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
          }}
        >
          {item.description}
        </Typography>
        
        <Box sx={{ mb: 1 }}>
          <Typography variant="h6" color="primary" fontWeight="bold">
            ${item.price.toFixed(2)}
          </Typography>
        </Box>

        {item.dietary_tags && item.dietary_tags.length > 0 && (
          <Stack direction="row" spacing={1} sx={{ mb: 1, flexWrap: 'wrap' }}>
            {item.dietary_tags.map((tag) => (
              <Chip key={tag} label={tag} size="small" color="success" />
            ))}
          </Stack>
        )}

        {item.preparation_time && (
          <Typography variant="caption" color="text.secondary">
            Prep time: {item.preparation_time} mins
          </Typography>
        )}
      </CardContent>

      <CardActions sx={{ justifyContent: 'space-between', px: 2, pb: 2 }}>
        <IconButton size="small" onClick={() => onViewDetails(item)}>
          <InfoIcon />
        </IconButton>

        {quantity > 0 ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton size="small" onClick={handleDecrement}>
              <RemoveIcon />
            </IconButton>
            <Typography variant="body1" sx={{ minWidth: 30, textAlign: 'center' }}>
              {quantity}
            </Typography>
            <IconButton size="small" onClick={handleIncrement}>
              <AddIcon />
            </IconButton>
          </Box>
        ) : (
          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            onClick={handleAddToCart}
            disabled={!item.is_available}
          >
            Add to Cart
          </Button>
        )}
      </CardActions>
    </Card>
  );
};