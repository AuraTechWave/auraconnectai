import React, { useState, useCallback } from 'react';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  IconButton,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Alert,
  Skeleton,
  Badge,
  SelectChangeEvent,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Search as SearchIcon,
  Download as DownloadIcon,
  Visibility as VisibilityIcon,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { useOrders } from '../../hooks/useOrders';
import { OrderStatus, PaymentStatus, OrderType, OrderListParams } from '../../types/order.types';
import { formatDate, getDateRange } from '../../utils/dateUtils';
import { debounce } from '../../utils/debounce';
import orderService from '../../services/orderService';

const OrderList: React.FC = () => {
  // Filter state
  const [filters, setFilters] = useState<OrderListParams>({
    limit: 25,
    offset: 0,
    include_items: false,
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);

  // Fetch orders with filters
  const { data, isLoading, error, refetch, newOrdersCount, resetNewOrdersCount } = useOrders(filters);

  // Debounced search
  const debouncedSearch = useCallback(
    debounce((query: string) => {
      setFilters(prev => ({ ...prev, search: query || undefined, offset: 0 }));
    }, 300),
    []
  );

  // Handle filter changes
  const handleStatusChange = (event: SelectChangeEvent<string>) => {
    const value = event.target.value;
    setFilters(prev => ({
      ...prev,
      status: value ? value as OrderStatus : undefined,
      offset: 0,
    }));
  };

  const handlePaymentStatusChange = (event: SelectChangeEvent<string>) => {
    const value = event.target.value;
    setFilters(prev => ({
      ...prev,
      payment_status: value ? value as PaymentStatus : undefined,
      offset: 0,
    }));
  };

  const handleDateRangeChange = () => {
    if (startDate && endDate) {
      const { start, end } = getDateRange(startDate, endDate);
      setFilters(prev => ({
        ...prev,
        date_from: start,
        date_to: end,
        offset: 0,
      }));
    }
  };

  // Handle pagination
  const handlePageChange = (event: unknown, newPage: number) => {
    setFilters(prev => ({
      ...prev,
      offset: newPage * (prev.limit || 25),
    }));
  };

  const handleRowsPerPageChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newLimit = parseInt(event.target.value, 10);
    setFilters(prev => ({
      ...prev,
      limit: newLimit,
      offset: 0,
    }));
  };

  // Export orders
  const handleExport = async (format: 'csv' | 'excel' | 'pdf') => {
    try {
      const blob = await orderService.exportOrders(format, filters);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `orders-${formatDate(new Date(), 'yyyy-MM-dd')}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Export failed:', error);
    }
  };

  // Handle new orders badge
  const handleRefresh = () => {
    resetNewOrdersCount();
    refetch();
  };

  // Get status color
  const getStatusColor = (status: OrderStatus) => {
    const colors: Record<OrderStatus, 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning'> = {
      [OrderStatus.PENDING]: 'warning',
      [OrderStatus.CONFIRMED]: 'info',
      [OrderStatus.IN_PROGRESS]: 'primary',
      [OrderStatus.READY]: 'secondary',
      [OrderStatus.COMPLETED]: 'success',
      [OrderStatus.CANCELLED]: 'error',
      [OrderStatus.DELAYED]: 'warning',
    };
    return colors[status] || 'default';
  };

  // Get payment status color
  const getPaymentStatusColor = (status: PaymentStatus) => {
    const colors: Record<PaymentStatus, 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning'> = {
      [PaymentStatus.PENDING]: 'warning',
      [PaymentStatus.PAID]: 'success',
      [PaymentStatus.PARTIAL]: 'info',
      [PaymentStatus.FAILED]: 'error',
      [PaymentStatus.REFUNDED]: 'secondary',
    };
    return colors[status] || 'default';
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Filters */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField
            size="small"
            placeholder="Search orders..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              debouncedSearch(e.target.value);
            }}
            InputProps={{
              startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
            }}
          />

          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Status</InputLabel>
            <Select
              value={filters.status || ''}
              onChange={handleStatusChange}
              label="Status"
            >
              <MenuItem value="">All</MenuItem>
              {Object.values(OrderStatus).map(status => (
                <MenuItem key={status} value={status}>
                  {status.replace('_', ' ').toUpperCase()}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Payment Status</InputLabel>
            <Select
              value={filters.payment_status || ''}
              onChange={handlePaymentStatusChange}
              label="Payment Status"
            >
              <MenuItem value="">All</MenuItem>
              {Object.values(PaymentStatus).map(status => (
                <MenuItem key={status} value={status}>
                  {status.replace('_', ' ').toUpperCase()}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <LocalizationProvider dateAdapter={AdapterDateFns}>
            <DatePicker
              label="Start Date"
              value={startDate}
              onChange={setStartDate}
              slotProps={{
                textField: { size: 'small' }
              }}
            />
            <DatePicker
              label="End Date"
              value={endDate}
              onChange={setEndDate}
              slotProps={{
                textField: { size: 'small' }
              }}
            />
          </LocalizationProvider>

          <Button
            size="small"
            variant="contained"
            onClick={handleDateRangeChange}
            disabled={!startDate || !endDate}
          >
            Apply Dates
          </Button>

          <Box sx={{ flexGrow: 1 }} />

          <Badge badgeContent={newOrdersCount} color="primary">
            <IconButton onClick={handleRefresh} size="small">
              <RefreshIcon />
            </IconButton>
          </Badge>

          <Button
            size="small"
            startIcon={<DownloadIcon />}
            onClick={() => handleExport('excel')}
          >
            Export
          </Button>
        </Box>
      </Paper>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error.message || 'Failed to load orders'}
        </Alert>
      )}

      {/* Orders Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Order #</TableCell>
              <TableCell>Customer</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Payment</TableCell>
              <TableCell align="right">Total</TableCell>
              <TableCell>Created</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              // Loading skeletons
              Array.from({ length: 5 }).map((_, index) => (
                <TableRow key={index}>
                  {Array.from({ length: 8 }).map((_, cellIndex) => (
                    <TableCell key={cellIndex}>
                      <Skeleton />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : data?.items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} align="center">
                  No orders found
                </TableCell>
              </TableRow>
            ) : (
              data?.items.map((order) => (
                <TableRow key={order.id} hover>
                  <TableCell>{order.order_number}</TableCell>
                  <TableCell>
                    {order.customer?.name || 'Walk-in'}
                    {order.table_no && ` (Table ${order.table_no})`}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={order.order_type.replace('_', ' ').toUpperCase()}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={order.status.replace('_', ' ').toUpperCase()}
                      color={getStatusColor(order.status)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={order.payment_status.replace('_', ' ').toUpperCase()}
                      color={getPaymentStatusColor(order.payment_status)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell align="right">${order.total.toFixed(2)}</TableCell>
                  <TableCell>{formatDate(order.created_at, 'MMM dd, HH:mm')}</TableCell>
                  <TableCell align="center">
                    <IconButton size="small">
                      <VisibilityIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={data?.total || 0}
          page={Math.floor((filters.offset || 0) / (filters.limit || 25))}
          onPageChange={handlePageChange}
          rowsPerPage={filters.limit || 25}
          onRowsPerPageChange={handleRowsPerPageChange}
          rowsPerPageOptions={[10, 25, 50, 100]}
        />
      </TableContainer>
    </Box>
  );
};

export default OrderList;