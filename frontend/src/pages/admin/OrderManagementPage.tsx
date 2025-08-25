import React from 'react';
import { Box, Container, Typography } from '@mui/material';
import OrderList from '../../components/admin/orders/OrderList';

const OrderManagementPage: React.FC = () => {
  return (
    <Container maxWidth={false} sx={{ py: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Order Management
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Manage restaurant orders, track status, and handle customer requests
        </Typography>
      </Box>
      
      <OrderList />
    </Container>
  );
};

export default OrderManagementPage;