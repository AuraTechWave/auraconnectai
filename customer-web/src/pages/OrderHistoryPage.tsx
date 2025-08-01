import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemText,
  Chip,
  IconButton,
  Collapse,
  Button,
  Alert,
  CircularProgress,
  TextField,
  InputAdornment,
} from '@mui/material';
import { Grid2 as Grid } from '../components/common/Grid2';
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Search as SearchIcon,
  Receipt as ReceiptIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';
import { Order } from '../types';

export const OrderHistoryPage: React.FC = () => {
  const { isAuthenticated } = useAuthStore();
  const [expandedOrder, setExpandedOrder] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const {
    data: ordersData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['order-history'],
    queryFn: api.getOrderHistory,
    enabled: isAuthenticated,
  });

  const orders = ordersData?.data || [];

  const filteredOrders = orders.filter((order: Order) => {
    const searchLower = searchQuery.toLowerCase();
    return (
      order.id.toString().includes(searchLower) ||
      order.status.toLowerCase().includes(searchLower) ||
      order.items.some((item) =>
        item.menu_item.name.toLowerCase().includes(searchLower)
      )
    );
  });

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'warning';
      case 'confirmed':
      case 'preparing':
        return 'info';
      case 'ready':
        return 'success';
      case 'delivered':
      case 'completed':
        return 'success';
      case 'cancelled':
        return 'error';
      default:
        return 'default';
    }
  };

  const handleExpandClick = (orderId: number) => {
    setExpandedOrder(expandedOrder === orderId ? null : orderId);
  };

  if (!isAuthenticated) {
    return (
      <Container>
        <Alert severity="info" sx={{ mt: 4 }}>
          Please login to view your order history.
        </Alert>
      </Container>
    );
  }

  if (error) {
    return (
      <Container>
        <Alert severity="error" sx={{ mt: 4 }}>
          Error loading order history. Please try again later.
        </Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h3" gutterBottom>
          Order History
        </Typography>
        <Typography variant="h6" color="text.secondary" paragraph>
          Track your orders and view past purchases
        </Typography>

        {/* Search Bar */}
        <TextField
          fullWidth
          placeholder="Search orders by ID, status, or items..."
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

        {isLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : filteredOrders.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <ReceiptIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h6" color="text.secondary">
              {searchQuery ? 'No orders found matching your search' : 'No orders yet'}
            </Typography>
            {!searchQuery && (
              <Button
                variant="contained"
                sx={{ mt: 2 }}
                href="/menu"
              >
                Start Ordering
              </Button>
            )}
          </Paper>
        ) : (
          <List>
            {filteredOrders.map((order: Order) => (
              <Paper key={order.id} sx={{ mb: 2 }}>
                <ListItem>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Typography variant="h6">
                          Order #{order.id}
                        </Typography>
                        <Chip
                          label={order.status}
                          color={getStatusColor(order.status) as any}
                          size="small"
                        />
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          {format(new Date(order.created_at), 'PPpp')}
                        </Typography>
                        <Typography variant="body2">
                          Total: ${order.total_amount.toFixed(2)} • {order.items.length} items
                        </Typography>
                      </Box>
                    }
                  />
                  <IconButton
                    onClick={() => handleExpandClick(order.id)}
                    aria-expanded={expandedOrder === order.id}
                    aria-label="show more"
                  >
                    {expandedOrder === order.id ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                  </IconButton>
                </ListItem>
                <Collapse in={expandedOrder === order.id} timeout="auto" unmountOnExit>
                  <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Order Details
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={12} md={8}>
                        <List dense>
                          {order.items.map((item) => (
                            <ListItem key={item.id}>
                              <ListItemText
                                primary={`${item.quantity}x ${item.menu_item.name}`}
                                secondary={
                                  <>
                                    ${item.price.toFixed(2)} each
                                    {item.special_instructions && (
                                      <Typography variant="caption" display="block">
                                        Note: {item.special_instructions}
                                      </Typography>
                                    )}
                                  </>
                                }
                              />
                              <Typography variant="body2">
                                ${(item.quantity * item.price).toFixed(2)}
                              </Typography>
                            </ListItem>
                          ))}
                        </List>
                      </Grid>
                      <Grid item xs={12} md={4}>
                        <Paper variant="outlined" sx={{ p: 2 }}>
                          <Typography variant="subtitle2" gutterBottom>
                            Order Summary
                          </Typography>
                          <Box sx={{ mt: 1 }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                              <Typography variant="body2">Subtotal:</Typography>
                              <Typography variant="body2">${order.total_amount.toFixed(2)}</Typography>
                            </Box>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                              <Typography variant="body2">Tax:</Typography>
                              <Typography variant="body2">$0.00</Typography>
                            </Box>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold' }}>
                              <Typography variant="body1">Total:</Typography>
                              <Typography variant="body1">${order.total_amount.toFixed(2)}</Typography>
                            </Box>
                          </Box>
                        </Paper>
                        {(order.status === 'pending' || order.status === 'confirmed') && (
                          <Button
                            variant="outlined"
                            fullWidth
                            sx={{ mt: 2 }}
                            onClick={() => alert('Track order feature coming soon!')}
                          >
                            Track Order
                          </Button>
                        )}
                      </Grid>
                    </Grid>
                  </Box>
                </Collapse>
              </Paper>
            ))}
          </List>
        )}
      </Box>
    </Container>
  );
};