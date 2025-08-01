import React, { useState } from 'react';
import {
  Box,
  TextField,
  Typography,
  FormControlLabel,
  Checkbox,
  Alert,
} from '@mui/material';
import { Grid2 as Grid } from '../common/Grid2';

interface PaymentFormProps {
  onPaymentChange: (valid: boolean, data: any) => void;
}

export const PaymentForm: React.FC<PaymentFormProps> = ({ onPaymentChange }) => {
  const [formData, setFormData] = useState({
    cardNumber: '',
    cardName: '',
    expiryDate: '',
    cvv: '',
    saveCard: false,
  });

  const [errors, setErrors] = useState<any>({});

  const validateForm = () => {
    const newErrors: any = {};

    // Card number validation (simple)
    if (!formData.cardNumber) {
      newErrors.cardNumber = 'Card number is required';
    } else if (formData.cardNumber.replace(/\s/g, '').length !== 16) {
      newErrors.cardNumber = 'Card number must be 16 digits';
    }

    // Card name validation
    if (!formData.cardName) {
      newErrors.cardName = 'Cardholder name is required';
    }

    // Expiry date validation
    if (!formData.expiryDate) {
      newErrors.expiryDate = 'Expiry date is required';
    } else if (!/^\d{2}\/\d{2}$/.test(formData.expiryDate)) {
      newErrors.expiryDate = 'Format: MM/YY';
    }

    // CVV validation
    if (!formData.cvv) {
      newErrors.cvv = 'CVV is required';
    } else if (!/^\d{3,4}$/.test(formData.cvv)) {
      newErrors.cvv = 'CVV must be 3 or 4 digits';
    }

    setErrors(newErrors);
    const isValid = Object.keys(newErrors).length === 0;
    
    if (isValid) {
      onPaymentChange(true, formData);
    } else {
      onPaymentChange(false, null);
    }

    return isValid;
  };

  const handleChange = (field: string, value: any) => {
    const newFormData = { ...formData, [field]: value };
    setFormData(newFormData);
    
    // Clear error for this field
    if (errors[field]) {
      setErrors({ ...errors, [field]: undefined });
    }

    // Validate on change
    setTimeout(() => validateForm(), 100);
  };

  const formatCardNumber = (value: string) => {
    const v = value.replace(/\s+/g, '').replace(/[^0-9]/gi, '');
    const matches = v.match(/\d{4,16}/g);
    const match = (matches && matches[0]) || '';
    const parts = [];

    for (let i = 0, len = match.length; i < len; i += 4) {
      parts.push(match.substring(i, i + 4));
    }

    if (parts.length) {
      return parts.join(' ');
    } else {
      return value;
    }
  };

  const formatExpiryDate = (value: string) => {
    const v = value.replace(/\s+/g, '').replace(/[^0-9]/gi, '');
    if (v.length >= 2) {
      return v.slice(0, 2) + (v.length > 2 ? '/' + v.slice(2, 4) : '');
    }
    return v;
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Payment Information
      </Typography>
      
      <Alert severity="info" sx={{ mb: 3 }}>
        This is a demo. Use card number: 4242 4242 4242 4242
      </Alert>

      <Grid container spacing={2}>
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Card Number"
            value={formData.cardNumber}
            onChange={(e) => handleChange('cardNumber', formatCardNumber(e.target.value))}
            error={!!errors.cardNumber}
            helperText={errors.cardNumber}
            inputProps={{ maxLength: 19 }}
            placeholder="1234 5678 9012 3456"
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Cardholder Name"
            value={formData.cardName}
            onChange={(e) => handleChange('cardName', e.target.value)}
            error={!!errors.cardName}
            helperText={errors.cardName}
            placeholder="John Doe"
          />
        </Grid>

        <Grid item xs={6}>
          <TextField
            fullWidth
            label="Expiry Date"
            value={formData.expiryDate}
            onChange={(e) => handleChange('expiryDate', formatExpiryDate(e.target.value))}
            error={!!errors.expiryDate}
            helperText={errors.expiryDate}
            inputProps={{ maxLength: 5 }}
            placeholder="MM/YY"
          />
        </Grid>

        <Grid item xs={6}>
          <TextField
            fullWidth
            label="CVV"
            value={formData.cvv}
            onChange={(e) => handleChange('cvv', e.target.value.replace(/\D/g, ''))}
            error={!!errors.cvv}
            helperText={errors.cvv}
            inputProps={{ maxLength: 4 }}
            placeholder="123"
          />
        </Grid>

        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Checkbox
                checked={formData.saveCard}
                onChange={(e) => handleChange('saveCard', e.target.checked)}
              />
            }
            label="Save card for future orders"
          />
        </Grid>
      </Grid>
    </Box>
  );
};