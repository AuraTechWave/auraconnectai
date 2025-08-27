import React, { useState } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Button,
  Chip,
  SelectChangeEvent,
  Collapse,
  Paper
} from '@mui/material';
import Grid from '@mui/material/GridLegacy';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { OrderStatus, PaymentStatus, OrderFilter } from '../../../types/order.types';

interface OrderFiltersProps {
  filters: OrderFilter;
  onFiltersChange: (filters: OrderFilter) => void;
  onClose: () => void;
}

const OrderFilters: React.FC<OrderFiltersProps> = ({
  filters,
  onFiltersChange,
  onClose
}) => {
  const [localFilters, setLocalFilters] = useState<OrderFilter>(filters);

  const handleStatusChange = (event: any) => {
    const value = event.target.value as string[];
    setLocalFilters({
      ...localFilters,
      status: value.length > 0 ? value as OrderStatus[] : undefined
    });
  };

  const handlePaymentStatusChange = (event: any) => {
    const value = event.target.value as string[];
    setLocalFilters({
      ...localFilters,
      payment_status: value.length > 0 ? value as PaymentStatus[] : undefined
    });
  };

  const handleOrderTypeChange = (event: any) => {
    const value = event.target.value as string[];
    setLocalFilters({
      ...localFilters,
      order_type: value.length > 0 ? value : undefined
    });
  };

  const handleDateFromChange = (date: Date | null) => {
    setLocalFilters({
      ...localFilters,
      date_from: date ? date.toISOString() : undefined
    });
  };

  const handleDateToChange = (date: Date | null) => {
    setLocalFilters({
      ...localFilters,
      date_to: date ? date.toISOString() : undefined
    });
  };

  const handleApply = () => {
    onFiltersChange(localFilters);
  };

  const handleClear = () => {
    setLocalFilters({});
    onFiltersChange({});
  };

  const orderStatuses = Object.values(OrderStatus);
  const paymentStatuses = Object.values(PaymentStatus);
  const orderTypes = ['dine_in', 'takeout', 'delivery'];

  return (
    <Collapse in={true}>
      <Paper sx={{ p: 2, mt: 2, backgroundColor: 'grey.50' }}>
        <LocalizationProvider dateAdapter={AdapterDateFns}>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Order Status</InputLabel>
                <Select
                  multiple
                  value={localFilters.status || []}
                  onChange={handleStatusChange}
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {(selected as string[]).map((value) => (
                        <Chip key={value} label={value} size="small" />
                      ))}
                    </Box>
                  )}
                >
                  {orderStatuses.map((status) => (
                    <MenuItem key={status} value={status}>
                      {status.replace('_', ' ')}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Payment Status</InputLabel>
                <Select
                  multiple
                  value={localFilters.payment_status || []}
                  onChange={handlePaymentStatusChange}
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {(selected as string[]).map((value) => (
                        <Chip key={value} label={value} size="small" />
                      ))}
                    </Box>
                  )}
                >
                  {paymentStatuses.map((status) => (
                    <MenuItem key={status} value={status}>
                      {status.replace('_', ' ')}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Order Type</InputLabel>
                <Select
                  multiple
                  value={localFilters.order_type || []}
                  onChange={handleOrderTypeChange}
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {(selected as string[]).map((value) => (
                        <Chip key={value} label={value.replace('_', ' ')} size="small" />
                      ))}
                    </Box>
                  )}
                >
                  {orderTypes.map((type) => (
                    <MenuItem key={type} value={type}>
                      {type.replace('_', ' ')}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <DatePicker
                label="From Date"
                value={localFilters.date_from ? new Date(localFilters.date_from) : null}
                onChange={handleDateFromChange}
                slotProps={{
                  textField: {
                    size: 'small',
                    fullWidth: true
                  }
                }}
              />
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <DatePicker
                label="To Date"
                value={localFilters.date_to ? new Date(localFilters.date_to) : null}
                onChange={handleDateToChange}
                slotProps={{
                  textField: {
                    size: 'small',
                    fullWidth: true
                  }
                }}
              />
            </Grid>

            <Grid item xs={12}>
              <Box display="flex" gap={2} justifyContent="flex-end">
                <Button onClick={handleClear} color="inherit">
                  Clear All
                </Button>
                <Button onClick={onClose} variant="outlined">
                  Cancel
                </Button>
                <Button onClick={handleApply} variant="contained">
                  Apply Filters
                </Button>
              </Box>
            </Grid>
          </Grid>
        </LocalizationProvider>
      </Paper>
    </Collapse>
  );
};

export default OrderFilters;