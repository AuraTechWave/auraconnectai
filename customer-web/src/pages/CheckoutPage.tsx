import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Paper,
  Stepper,
  Step,
  StepLabel,
  Button,
  Alert,
  List,
  ListItem,
  ListItemText,
  Divider,
  CircularProgress,
  RadioGroup,
  FormControlLabel,
  Radio,
  TextField,
} from '@mui/material';
import { Grid2 as Grid } from '../components/common/Grid2';
import { PaymentForm } from '../components/payment/PaymentForm';
import { useCartStore } from '../store/cartStore';
import { useAuthStore } from '../store/authStore';
import { toast } from 'react-toastify';
import api from '../services/api';

const steps = ['Order Type', 'Payment', 'Review & Confirm'];

export const CheckoutPage: React.FC = () => {
  const navigate = useNavigate();
  const { items, getTotal, clearCart } = useCartStore();
  const { customer } = useAuthStore();
  const [activeStep, setActiveStep] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  
  const [orderData, setOrderData] = useState({
    orderType: 'pickup',
    deliveryAddress: '',
    specialInstructions: '',
    paymentValid: false,
    paymentData: null,
  });

  const total = getTotal();
  const tax = total * 0.085;
  const deliveryFee = orderData.orderType === 'delivery' ? 5 : 0;
  const finalTotal = total + tax + deliveryFee;

  if (items.length === 0) {
    navigate('/cart');
    return null;
  }

  const handleNext = () => {
    if (activeStep === steps.length - 1) {
      handlePlaceOrder();
    } else {
      setActiveStep((prevActiveStep) => prevActiveStep + 1);
    }
  };

  const handleBack = () => {
    setActiveStep((prevActiveStep) => prevActiveStep - 1);
  };

  const handlePlaceOrder = async () => {
    setIsProcessing(true);
    try {
      const order = {
        items: items.map(item => ({
          menu_item_id: item.menuItem.id,
          quantity: item.quantity,
          price: item.menuItem.price,
          special_instructions: item.specialInstructions,
        })),
        order_type: orderData.orderType,
        delivery_address: orderData.deliveryAddress,
        special_instructions: orderData.specialInstructions,
        payment_method: 'card',
        payment_data: orderData.paymentData,
      };

      const response = await api.createOrder(order);
      clearCart();
      toast.success('Order placed successfully!');
      navigate(`/orders/${response.data.id}`);
    } catch (error) {
      toast.error('Failed to place order. Please try again.');
      console.error('Order error:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const isStepValid = (step: number) => {
    switch (step) {
      case 0:
        return orderData.orderType && (orderData.orderType !== 'delivery' || orderData.deliveryAddress);
      case 1:
        return orderData.paymentValid;
      case 2:
        return true;
      default:
        return false;
    }
  };

  const getStepContent = (step: number) => {
    switch (step) {
      case 0:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              How would you like to receive your order?
            </Typography>
            <RadioGroup
              value={orderData.orderType}
              onChange={(e) => setOrderData({ ...orderData, orderType: e.target.value })}
            >
              <FormControlLabel
                value="pickup"
                control={<Radio />}
                label={
                  <Box>
                    <Typography variant="body1">Pickup</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Ready in 20-30 minutes
                    </Typography>
                  </Box>
                }
              />
              <FormControlLabel
                value="delivery"
                control={<Radio />}
                label={
                  <Box>
                    <Typography variant="body1">Delivery</Typography>
                    <Typography variant="caption" color="text.secondary">
                      45-60 minutes • $5.00 delivery fee
                    </Typography>
                  </Box>
                }
              />
            </RadioGroup>

            {orderData.orderType === 'delivery' && (
              <TextField
                fullWidth
                multiline
                rows={3}
                label="Delivery Address"
                value={orderData.deliveryAddress}
                onChange={(e) => setOrderData({ ...orderData, deliveryAddress: e.target.value })}
                sx={{ mt: 2 }}
                required
              />
            )}

            <TextField
              fullWidth
              multiline
              rows={2}
              label="Special Instructions (Optional)"
              value={orderData.specialInstructions}
              onChange={(e) => setOrderData({ ...orderData, specialInstructions: e.target.value })}
              sx={{ mt: 2 }}
              placeholder="Any special requests or dietary requirements..."
            />
          </Box>
        );

      case 1:
        return (
          <PaymentForm
            onPaymentChange={(valid, data) => {
              setOrderData({ ...orderData, paymentValid: valid, paymentData: data });
            }}
          />
        );

      case 2:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Order Summary
            </Typography>
            
            <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                {orderData.orderType === 'pickup' ? 'Pickup Order' : 'Delivery Order'}
              </Typography>
              {orderData.deliveryAddress && (
                <Typography variant="body2" color="text.secondary">
                  Deliver to: {orderData.deliveryAddress}
                </Typography>
              )}
              {orderData.specialInstructions && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Special instructions: {orderData.specialInstructions}
                </Typography>
              )}
            </Paper>

            <List dense>
              {items.map((item) => (
                <ListItem key={item.menuItem.id}>
                  <ListItemText
                    primary={`${item.quantity}x ${item.menuItem.name}`}
                    secondary={item.specialInstructions}
                  />
                  <Typography variant="body2">
                    ${(item.quantity * item.menuItem.price).toFixed(2)}
                  </Typography>
                </ListItem>
              ))}
            </List>

            <Divider sx={{ my: 2 }} />

            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2">Subtotal:</Typography>
              <Typography variant="body2">${total.toFixed(2)}</Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2">Tax:</Typography>
              <Typography variant="body2">${tax.toFixed(2)}</Typography>
            </Box>
            {deliveryFee > 0 && (
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography variant="body2">Delivery Fee:</Typography>
                <Typography variant="body2">${deliveryFee.toFixed(2)}</Typography>
              </Box>
            )}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1, pt: 1, borderTop: 1, borderColor: 'divider' }}>
              <Typography variant="h6">Total:</Typography>
              <Typography variant="h6">${finalTotal.toFixed(2)}</Typography>
            </Box>
          </Box>
        );

      default:
        return 'Unknown step';
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h3" gutterBottom>
          Checkout
        </Typography>

        <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        <Grid container spacing={3}>
          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 3 }}>
              {getStepContent(activeStep)}
            </Paper>
          </Grid>

          <Grid item xs={12} md={4}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Order Total
              </Typography>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography variant="body2">Subtotal:</Typography>
                <Typography variant="body2">${total.toFixed(2)}</Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography variant="body2">Tax:</Typography>
                <Typography variant="body2">${tax.toFixed(2)}</Typography>
              </Box>
              {deliveryFee > 0 && (
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography variant="body2">Delivery Fee:</Typography>
                  <Typography variant="body2">${deliveryFee.toFixed(2)}</Typography>
                </Box>
              )}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
                <Typography variant="h6">Total:</Typography>
                <Typography variant="h6">${finalTotal.toFixed(2)}</Typography>
              </Box>
            </Paper>
          </Grid>
        </Grid>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
          <Button
            disabled={activeStep === 0}
            onClick={handleBack}
          >
            Back
          </Button>
          <Button
            variant="contained"
            onClick={handleNext}
            disabled={!isStepValid(activeStep) || isProcessing}
          >
            {isProcessing ? (
              <CircularProgress size={24} />
            ) : activeStep === steps.length - 1 ? (
              'Place Order'
            ) : (
              'Next'
            )}
          </Button>
        </Box>
      </Box>
    </Container>
  );
};