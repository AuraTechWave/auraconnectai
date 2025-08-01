import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Paper,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Card,
  CardContent,
  Alert,
  CircularProgress,
  Button,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import { Grid2 as Grid } from '../components/common/Grid2';
import {
  CheckCircle as CheckCircleIcon,
  Restaurant as RestaurantIcon,
  LocalShipping as LocalShippingIcon,
  AccessTime as AccessTimeIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import { Order } from '../types';

const orderSteps = [
  {
    label: 'Order Placed',
    description: 'Your order has been received',
    icon: CheckCircleIcon,
    status: ['pending'],
  },
  {
    label: 'Order Confirmed',
    description: 'Restaurant has confirmed your order',
    icon: RestaurantIcon,
    status: ['confirmed'],
  },
  {
    label: 'Preparing',
    description: 'Your food is being prepared',
    icon: RestaurantIcon,
    status: ['preparing'],
  },
  {
    label: 'Ready for Pickup/Delivery',
    description: 'Your order is ready',
    icon: LocalShippingIcon,
    status: ['ready'],
  },
  {
    label: 'Completed',
    description: 'Order delivered successfully',
    icon: CheckCircleIcon,
    status: ['delivered', 'completed'],
  },
];

export const OrderTrackingPage: React.FC = () => {
  const { orderId } = useParams<{ orderId: string }>();
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);

  const {
    data: orderData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['order', orderId],
    queryFn: () => api.getOrder(Number(orderId)),
    refetchInterval: 30000, // Refetch every 30 seconds
    enabled: !!orderId,
  });

  const order = orderData?.data;

  useEffect(() => {
    if (order) {
      const currentStepIndex = orderSteps.findIndex((step) =>
        step.status.includes(order.status.toLowerCase())
      );
      setActiveStep(currentStepIndex >= 0 ? currentStepIndex : 0);
    }
  }, [order]);

  if (!orderId) {
    return (
      <Container>
        <Alert severity="error" sx={{ mt: 4 }}>
          Invalid order ID
        </Alert>
      </Container>
    );
  }

  if (error) {
    return (
      <Container>
        <Alert severity="error" sx={{ mt: 4 }}>
          Error loading order details. Please try again later.
        </Alert>
      </Container>
    );
  }

  if (isLoading) {
    return (
      <Container>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (!order) {
    return (
      <Container>
        <Alert severity="error" sx={{ mt: 4 }}>
          Order not found
        </Alert>
      </Container>
    );
  }

  const estimatedTime = new Date(order.created_at);
  estimatedTime.setMinutes(estimatedTime.getMinutes() + 45);

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h3" gutterBottom>
          Track Order #{order.id}
        </Typography>
        <Typography variant="h6" color="text.secondary" paragraph>
          Real-time order tracking
        </Typography>

        <Grid container spacing={3}>
          {/* Order Status Timeline */}
          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Order Status
              </Typography>
              <Stepper activeStep={activeStep} orientation="vertical">
                {orderSteps.map((step, index) => (
                  <Step key={step.label}>
                    <StepLabel
                      optional={
                        index === activeStep && (
                          <Typography variant="caption">Current status</Typography>
                        )
                      }
                    >
                      {step.label}
                    </StepLabel>
                    <StepContent>
                      <Typography>{step.description}</Typography>
                      {index === activeStep && (
                        <Box sx={{ mb: 2, mt: 1 }}>
                          <Alert severity="info" icon={<AccessTimeIcon />}>
                            Estimated completion: {format(estimatedTime, 'p')}
                          </Alert>
                        </Box>
                      )}
                    </StepContent>
                  </Step>
                ))}
              </Stepper>
            </Paper>

            {/* Order Items */}
            <Paper sx={{ p: 3, mt: 3 }}>
              <Typography variant="h6" gutterBottom>
                Order Items
              </Typography>
              <List>
                {order.items.map((item: any) => (
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
            </Paper>
          </Grid>

          {/* Order Summary Sidebar */}
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Order Summary
                </Typography>
                <Box sx={{ mt: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">Order Date:</Typography>
                    <Typography variant="body2">
                      {format(new Date(order.created_at), 'PPp')}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">Order Type:</Typography>
                    <Typography variant="body2">{order.order_type || 'Pickup'}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">Payment Status:</Typography>
                    <Typography variant="body2">{order.payment_status || 'Paid'}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">Total Items:</Typography>
                    <Typography variant="body2">{order.items.length}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
                    <Typography variant="h6">Total:</Typography>
                    <Typography variant="h6">${order.total_amount.toFixed(2)}</Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>

            <Button
              variant="contained"
              fullWidth
              sx={{ mt: 2 }}
              onClick={() => navigate('/orders')}
            >
              View All Orders
            </Button>

            <Button
              variant="outlined"
              fullWidth
              sx={{ mt: 1 }}
              onClick={() => refetch()}
            >
              Refresh Status
            </Button>

            {order.status === 'delivered' && (
              <Button
                variant="outlined"
                fullWidth
                sx={{ mt: 1 }}
                onClick={() => alert('Rate order feature coming soon!')}
              >
                Rate Your Order
              </Button>
            )}
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
};