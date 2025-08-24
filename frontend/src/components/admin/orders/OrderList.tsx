import React, { useState, useEffect, useCallback } from 'react';
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
  InputAdornment,
  Button,
  Menu,
  MenuItem,
  Tooltip,
  Typography,
  CircularProgress,
  Alert
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Refresh as RefreshIcon,
  MoreVert as MoreVertIcon,
  Visibility as ViewIcon,
  Edit as EditIcon,
  Cancel as CancelIcon,
  Download as DownloadIcon
} from '@mui/icons-material';
import { format } from 'date-fns';
import { Order, OrderStatus, PaymentStatus } from '@/types/order.types';
import { orderService } from '@/services/orderService';
import websocketService from '@/services/websocketService';
import OrderFilters from './OrderFilters';
import OrderDetails from './OrderDetails';
import OrderStatusChip from './OrderStatusChip';
import PaymentStatusChip from './PaymentStatusChip';

const OrderList: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState({});
  const [showFilters, setShowFilters] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [showOrderDetails, setShowOrderDetails] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  // Fetch orders
  const fetchOrders = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await orderService.getOrders({
        ...filters,
        search: searchQuery
      });
      setOrders(data);
      setTotalCount(data.length);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch orders');
    } finally {
      setLoading(false);
    }
  }, [filters, searchQuery]);

  // Initial load and WebSocket setup
  useEffect(() => {
    fetchOrders();
    
    // Setup WebSocket connection
    const restaurantId = localStorage.getItem('restaurantId') || '1';
    websocketService.connect(restaurantId);
    websocketService.subscribeToOrders(restaurantId);
    
    // WebSocket event handlers
    const handleNewOrder = (order: Order) => {
      setOrders(prev => [order, ...prev]);
      setTotalCount(prev => prev + 1);
    };
    
    const handleOrderUpdate = (order: Order) => {
      setOrders(prev => prev.map(o => o.id === order.id ? order : o));
    };
    
    const handleOrderStatusChange = (data: { orderId: string; status: string; order: Order }) => {
      setOrders(prev => prev.map(o => o.id === data.orderId ? data.order : o));
    };
    
    const handleConnectionStatus = (connected: boolean) => {
      setWsConnected(connected);
    };
    
    websocketService.on('connected', handleConnectionStatus);
    websocketService.on('order:new', handleNewOrder);
    websocketService.on('order:updated', handleOrderUpdate);
    websocketService.on('order:status_changed', handleOrderStatusChange);
    
    return () => {
      websocketService.off('connected', handleConnectionStatus);
      websocketService.off('order:new', handleNewOrder);
      websocketService.off('order:updated', handleOrderUpdate);
      websocketService.off('order:status_changed', handleOrderStatusChange);
      websocketService.unsubscribeFromOrders(restaurantId);
    };
  }, []);

  // Re-fetch when filters or search changes
  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, orderId: string) => {
    setAnchorEl(event.currentTarget);
    setSelectedOrderId(orderId);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedOrderId(null);
  };

  const handleViewOrder = (order: Order) => {
    setSelectedOrder(order);
    setShowOrderDetails(true);
    handleMenuClose();
  };

  const handleStatusChange = async (orderId: string, newStatus: OrderStatus) => {
    try {
      await orderService.updateOrderStatus(orderId, newStatus);
      // WebSocket will handle the update
    } catch (err: any) {
      setError(err.message || 'Failed to update order status');
    }
  };

  const handleCancelOrder = async (orderId: string) => {
    if (window.confirm('Are you sure you want to cancel this order?')) {
      try {
        await orderService.cancelOrder(orderId);
        // WebSocket will handle the update
        handleMenuClose();
      } catch (err: any) {
        setError(err.message || 'Failed to cancel order');
      }
    }
  };

  const handleExportOrders = async () => {
    try {
      const blob = await orderService.exportOrders(filters);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `orders_${format(new Date(), 'yyyy-MM-dd_HH-mm-ss')}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setError(err.message || 'Failed to export orders');
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  if (loading && orders.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box mb={3}>
        <Typography variant="h4" gutterBottom>
          Order Management
        </Typography>
        {wsConnected && (
          <Chip 
            label="Live Updates Active" 
            color="success" 
            size="small"
            sx={{ mb: 2 }}
          />
        )}
      </Box>

      {/* Search and Actions Bar */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box display="flex" gap={2} alignItems="center">
          <TextField
            placeholder="Search orders..."
            value={searchQuery}
            onChange={handleSearchChange}
            size="small"
            sx={{ flex: 1, maxWidth: 400 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
          />
          <Button
            startIcon={<FilterIcon />}
            onClick={() => setShowFilters(!showFilters)}
            variant={Object.keys(filters).length > 0 ? "contained" : "outlined"}
          >
            Filters {Object.keys(filters).length > 0 && `(${Object.keys(filters).length})`}
          </Button>
          <Button
            startIcon={<RefreshIcon />}
            onClick={fetchOrders}
          >
            Refresh
          </Button>
          <Button
            startIcon={<DownloadIcon />}
            onClick={handleExportOrders}
            variant="outlined"
          >
            Export
          </Button>
        </Box>
        
        {/* Filters */}
        {showFilters && (
          <OrderFilters
            filters={filters}
            onFiltersChange={setFilters}
            onClose={() => setShowFilters(false)}
          />
        )}
      </Paper>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Orders Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Order #</TableCell>
              <TableCell>Date/Time</TableCell>
              <TableCell>Customer</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Items</TableCell>
              <TableCell align="right">Total</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Payment</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {orders
              .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
              .map((order) => (
                <TableRow key={order.id} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight="bold">
                      {order.order_number}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {format(new Date(order.created_at), 'MMM dd, yyyy')}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {format(new Date(order.created_at), 'HH:mm')}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {order.customer_name || 'Walk-in'}
                    </Typography>
                    {order.table_number && (
                      <Typography variant="caption" color="text.secondary">
                        Table {order.table_number}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={order.order_type.replace('_', ' ')}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {order.items.length} items
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" fontWeight="bold">
                      {formatCurrency(order.total)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <OrderStatusChip
                      status={order.status}
                      onChange={(newStatus) => handleStatusChange(order.id, newStatus)}
                    />
                  </TableCell>
                  <TableCell>
                    <PaymentStatusChip status={order.payment_status} />
                  </TableCell>
                  <TableCell align="center">
                    <IconButton
                      size="small"
                      onClick={(e) => handleMenuOpen(e, order.id)}
                    >
                      <MoreVertIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
        <TablePagination
          rowsPerPageOptions={[10, 25, 50, 100]}
          component="div"
          count={totalCount}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </TableContainer>

      {/* Action Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem 
          onClick={() => {
            const order = orders.find(o => o.id === selectedOrderId);
            if (order) handleViewOrder(order);
          }}
        >
          <ViewIcon sx={{ mr: 1 }} fontSize="small" />
          View Details
        </MenuItem>
        <MenuItem 
          onClick={() => {
            const order = orders.find(o => o.id === selectedOrderId);
            if (order) {
              setSelectedOrder(order);
              setShowOrderDetails(true);
            }
            handleMenuClose();
          }}
        >
          <EditIcon sx={{ mr: 1 }} fontSize="small" />
          Edit Order
        </MenuItem>
        <MenuItem 
          onClick={() => selectedOrderId && handleCancelOrder(selectedOrderId)}
          sx={{ color: 'error.main' }}
        >
          <CancelIcon sx={{ mr: 1 }} fontSize="small" />
          Cancel Order
        </MenuItem>
      </Menu>

      {/* Order Details Dialog */}
      {showOrderDetails && selectedOrder && (
        <OrderDetails
          order={selectedOrder}
          open={showOrderDetails}
          onClose={() => {
            setShowOrderDetails(false);
            setSelectedOrder(null);
          }}
          onUpdate={fetchOrders}
        />
      )}
    </Box>
  );
};

export default OrderList;