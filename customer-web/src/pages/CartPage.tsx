import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Button,
  Divider,
  TextField,
  Grid,
  Alert,
} from '@mui/material';
import {
  Add as AddIcon,
  Remove as RemoveIcon,
  Delete as DeleteIcon,
  ShoppingCart as ShoppingCartIcon,
} from '@mui/icons-material';
import { useCartStore } from '../store/cartStore';
import { useAuthStore } from '../store/authStore';

export const CartPage: React.FC = () => {
  const navigate = useNavigate();
  const { items, getTotal, updateItemQuantity, removeItem, clearCart } = useCartStore();
  const { isAuthenticated } = useAuthStore();
  const total = getTotal();

  const handleCheckout = () => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: '/checkout' } });
    } else {
      navigate('/checkout');
    }
  };

  if (items.length === 0) {
    return (
      <Container maxWidth="md" sx={{ py: 8, textAlign: 'center' }}>
        <ShoppingCartIcon sx={{ fontSize: 80, color: 'grey.400', mb: 2 }} />
        <Typography variant="h4" gutterBottom>
          Your cart is empty
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          Add some delicious items from our menu
        </Typography>
        <Button
          variant="contained"
          size="large"
          component={Link}
          to="/menu"
          sx={{ mt: 2 }}
        >
          Browse Menu
        </Button>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom>
        Shopping Cart
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 2 }}>
            <List>
              {items.map((item, index) => (
                <React.Fragment key={item.menuItem.id}>
                  {index > 0 && <Divider />}
                  <ListItem sx={{ py: 2 }}>
                    <ListItemText
                      primary={
                        <Typography variant="h6">{item.menuItem.name}</Typography>
                      }
                      secondary={
                        <Box>
                          <Typography variant="body2" color="text.secondary">
                            ${item.menuItem.price.toFixed(2)} each
                          </Typography>
                          {item.modifiers && item.modifiers.length > 0 && (
                            <Typography variant="body2" color="text.secondary">
                              Modifiers: {item.modifiers.map(m => m.name).join(', ')}
                            </Typography>
                          )}
                          {item.specialInstructions && (
                            <Typography variant="body2" color="text.secondary">
                              Note: {item.specialInstructions}
                            </Typography>
                          )}
                        </Box>
                      }
                    />
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <IconButton
                          size="small"
                          onClick={() =>
                            updateItemQuantity(item.menuItem.id, item.quantity - 1)
                          }
                        >
                          <RemoveIcon />
                        </IconButton>
                        <Typography sx={{ mx: 2, minWidth: 30, textAlign: 'center' }}>
                          {item.quantity}
                        </Typography>
                        <IconButton
                          size="small"
                          onClick={() =>
                            updateItemQuantity(item.menuItem.id, item.quantity + 1)
                          }
                        >
                          <AddIcon />
                        </IconButton>
                      </Box>
                      <Typography variant="h6" sx={{ minWidth: 80, textAlign: 'right' }}>
                        ${item.subtotal.toFixed(2)}
                      </Typography>
                      <IconButton
                        color="error"
                        onClick={() => removeItem(item.menuItem.id)}
                      >
                        <DeleteIcon />
                      </IconButton>
                    </Box>
                  </ListItem>
                </React.Fragment>
              ))}
            </List>

            <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between' }}>
              <Button
                variant="text"
                color="error"
                onClick={clearCart}
              >
                Clear Cart
              </Button>
              <Button
                variant="outlined"
                component={Link}
                to="/menu"
              >
                Continue Shopping
              </Button>
            </Box>
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, position: 'sticky', top: 100 }}>
            <Typography variant="h6" gutterBottom>
              Order Summary
            </Typography>
            
            <Box sx={{ mt: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography>Subtotal</Typography>
                <Typography>${total.toFixed(2)}</Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography>Tax (8.5%)</Typography>
                <Typography>${(total * 0.085).toFixed(2)}</Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography>Service Fee</Typography>
                <Typography>$2.00</Typography>
              </Box>
              
              <Divider sx={{ my: 2 }} />
              
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="h6">Total</Typography>
                <Typography variant="h6">
                  ${(total + total * 0.085 + 2).toFixed(2)}
                </Typography>
              </Box>

              <TextField
                fullWidth
                placeholder="Promo code"
                size="small"
                sx={{ mb: 2 }}
              />

              {!isAuthenticated && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  Please login to complete your order
                </Alert>
              )}

              <Button
                variant="contained"
                fullWidth
                size="large"
                onClick={handleCheckout}
              >
                Proceed to Checkout
              </Button>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
};