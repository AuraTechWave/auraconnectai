import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Divider,
  Button,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Alert,
  Tab,
  Tabs,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction
} from '@mui/material';
import Grid from '@mui/material/GridLegacy';
import {
  Close as CloseIcon,
  Edit as EditIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
  Print as PrintIcon,
  Receipt as ReceiptIcon,
  History as HistoryIcon,
  AttachMoney as MoneyIcon
} from '@mui/icons-material';
import { format } from 'date-fns';
import { Order, OrderStatus } from '../../../types/order.types';
import { orderService } from '../../../services/orderService';
import OrderStatusChip from './OrderStatusChip';
import PaymentStatusChip from './PaymentStatusChip';

interface OrderDetailsProps {
  order: Order;
  open: boolean;
  onClose: () => void;
  onUpdate: () => void;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div hidden={value !== index}>
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
};

const OrderDetails: React.FC<OrderDetailsProps> = ({
  order: initialOrder,
  open,
  onClose,
  onUpdate
}) => {
  const [order, setOrder] = useState<Order>(initialOrder);
  const [isEditing, setIsEditing] = useState(false);
  const [editedOrder, setEditedOrder] = useState<Order>(initialOrder);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tabValue, setTabValue] = useState(0);
  const [refundAmount, setRefundAmount] = useState('');
  const [refundReason, setRefundReason] = useState('');

  const handleEdit = () => {
    setIsEditing(true);
    setEditedOrder(order);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedOrder(order);
    setError(null);
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      setError(null);
      const updatedOrder = await orderService.updateOrder(order.id, editedOrder);
      setOrder(updatedOrder);
      setIsEditing(false);
      onUpdate();
    } catch (err: any) {
      setError(err.message || 'Failed to update order');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (newStatus: OrderStatus) => {
    try {
      setLoading(true);
      setError(null);
      const updatedOrder = await orderService.updateOrderStatus(order.id, newStatus);
      setOrder(updatedOrder);
      onUpdate();
    } catch (err: any) {
      setError(err.message || 'Failed to update status');
    } finally {
      setLoading(false);
    }
  };

  const handleRefund = async () => {
    if (!refundAmount || parseFloat(refundAmount) <= 0) {
      setError('Please enter a valid refund amount');
      return;
    }
    
    try {
      setLoading(true);
      setError(null);
      const result = await orderService.refundOrder(
        order.id,
        parseFloat(refundAmount),
        refundReason
      );
      // Check if result is an Order or RefundResponse
      if ('order_number' in result) {
        setOrder(result as Order);
      }
      setRefundAmount('');
      setRefundReason('');
      onUpdate();
    } catch (err: any) {
      setError(err.message || 'Failed to process refund');
    } finally {
      setLoading(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { minHeight: '80vh' }
      }}
    >
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h5">
            Order #{order.order_number}
          </Typography>
          <Box display="flex" gap={1} alignItems="center">
            {!isEditing ? (
              <>
                <IconButton onClick={handlePrint} size="small">
                  <PrintIcon />
                </IconButton>
                <IconButton onClick={handleEdit} size="small">
                  <EditIcon />
                </IconButton>
              </>
            ) : (
              <>
                <Button
                  startIcon={<SaveIcon />}
                  onClick={handleSave}
                  variant="contained"
                  size="small"
                  disabled={loading}
                >
                  Save
                </Button>
                <Button
                  startIcon={<CancelIcon />}
                  onClick={handleCancelEdit}
                  size="small"
                  disabled={loading}
                >
                  Cancel
                </Button>
              </>
            )}
            <IconButton onClick={onClose} size="small">
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        {error && (
          <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
          <Tab label="Order Details" icon={<ReceiptIcon />} iconPosition="start" />
          <Tab label="Payment & Refunds" icon={<MoneyIcon />} iconPosition="start" />
          <Tab label="History" icon={<HistoryIcon />} iconPosition="start" />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          {/* Order Information */}
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="text.secondary">
                Order Information
              </Typography>
              <Box mt={1}>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary">
                      Date & Time
                    </Typography>
                    <Typography variant="body1">
                      {format(new Date(order.created_at), 'MMM dd, yyyy HH:mm')}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary">
                      Order Type
                    </Typography>
                    <Typography variant="body1">
                      {order.order_type.replace('_', ' ')}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary">
                      Status
                    </Typography>
                    <Box mt={0.5}>
                      <OrderStatusChip
                        status={order.status}
                        onChange={handleStatusChange}
                        readOnly={isEditing}
                      />
                    </Box>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary">
                      Payment Status
                    </Typography>
                    <Box mt={0.5}>
                      <PaymentStatusChip status={order.payment_status} />
                    </Box>
                  </Grid>
                  {order.table_number && (
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">
                        Table Number
                      </Typography>
                      {isEditing ? (
                        <TextField
                          size="small"
                          value={editedOrder.table_number}
                          onChange={(e) => setEditedOrder({
                            ...editedOrder,
                            table_number: e.target.value
                          })}
                          fullWidth
                        />
                      ) : (
                        <Typography variant="body1">
                          {order.table_number}
                        </Typography>
                      )}
                    </Grid>
                  )}
                </Grid>
              </Box>
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="text.secondary">
                Customer Information
              </Typography>
              <Box mt={1}>
                <Grid container spacing={2}>
                  <Grid item xs={12}>
                    <Typography variant="body2" color="text.secondary">
                      Name
                    </Typography>
                    {isEditing ? (
                      <TextField
                        size="small"
                        value={editedOrder.customer_name || ''}
                        onChange={(e) => setEditedOrder({
                          ...editedOrder,
                          customer_name: e.target.value
                        })}
                        fullWidth
                      />
                    ) : (
                      <Typography variant="body1">
                        {order.customer_name || 'Walk-in Customer'}
                      </Typography>
                    )}
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary">
                      Phone
                    </Typography>
                    {isEditing ? (
                      <TextField
                        size="small"
                        value={editedOrder.customer_phone || ''}
                        onChange={(e) => setEditedOrder({
                          ...editedOrder,
                          customer_phone: e.target.value
                        })}
                        fullWidth
                      />
                    ) : (
                      <Typography variant="body1">
                        {order.customer_phone || '-'}
                      </Typography>
                    )}
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary">
                      Email
                    </Typography>
                    {isEditing ? (
                      <TextField
                        size="small"
                        value={editedOrder.customer_email || ''}
                        onChange={(e) => setEditedOrder({
                          ...editedOrder,
                          customer_email: e.target.value
                        })}
                        fullWidth
                      />
                    ) : (
                      <Typography variant="body1">
                        {order.customer_email || '-'}
                      </Typography>
                    )}
                  </Grid>
                </Grid>
              </Box>
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          {/* Order Items */}
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Order Items
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Item</TableCell>
                  <TableCell align="center">Qty</TableCell>
                  <TableCell align="right">Unit Price</TableCell>
                  <TableCell align="right">Total</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {order.items.map((item, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <Typography variant="body2">
                        {item.menu_item_name}
                      </Typography>
                      {item.special_instructions && (
                        <Typography variant="caption" color="text.secondary">
                          Note: {item.special_instructions}
                        </Typography>
                      )}
                      {item.modifiers && item.modifiers.length > 0 && (
                        <Typography variant="caption" color="text.secondary" display="block">
                          Modifiers: {item.modifiers.map(m => m.name).join(', ')}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell align="center">{item.quantity}</TableCell>
                    <TableCell align="right">
                      {formatCurrency(item.unit_price)}
                    </TableCell>
                    <TableCell align="right">
                      {formatCurrency(item.total_price)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {/* Order Summary */}
          <Box mt={3}>
            <Grid container spacing={1}>
              <Grid item xs={8} textAlign="right">
                <Typography variant="body2">Subtotal:</Typography>
              </Grid>
              <Grid item xs={4} textAlign="right">
                <Typography variant="body2">
                  {formatCurrency(order.subtotal)}
                </Typography>
              </Grid>
              <Grid item xs={8} textAlign="right">
                <Typography variant="body2">Tax:</Typography>
              </Grid>
              <Grid item xs={4} textAlign="right">
                <Typography variant="body2">
                  {formatCurrency(order.tax)}
                </Typography>
              </Grid>
              {order.tip && order.tip > 0 && (
                <>
                  <Grid item xs={8} textAlign="right">
                    <Typography variant="body2">Tip:</Typography>
                  </Grid>
                  <Grid item xs={4} textAlign="right">
                    <Typography variant="body2">
                      {formatCurrency(order.tip)}
                    </Typography>
                  </Grid>
                </>
              )}
              {order.discount && order.discount > 0 && (
                <>
                  <Grid item xs={8} textAlign="right">
                    <Typography variant="body2">Discount:</Typography>
                  </Grid>
                  <Grid item xs={4} textAlign="right">
                    <Typography variant="body2" color="error">
                      -{formatCurrency(order.discount)}
                    </Typography>
                  </Grid>
                </>
              )}
              <Grid item xs={8} textAlign="right">
                <Typography variant="h6">Total:</Typography>
              </Grid>
              <Grid item xs={4} textAlign="right">
                <Typography variant="h6">
                  {formatCurrency(order.total)}
                </Typography>
              </Grid>
            </Grid>
          </Box>

          {/* Notes */}
          {(order.notes || isEditing) && (
            <Box mt={3}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Notes
              </Typography>
              {isEditing ? (
                <TextField
                  multiline
                  rows={3}
                  value={editedOrder.notes || ''}
                  onChange={(e) => setEditedOrder({
                    ...editedOrder,
                    notes: e.target.value
                  })}
                  fullWidth
                  variant="outlined"
                  size="small"
                />
              ) : (
                <Typography variant="body2">
                  {order.notes || 'No notes'}
                </Typography>
              )}
            </Box>
          )}
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          {/* Payment Information */}
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Payment Information
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={6}>
              <Typography variant="body2" color="text.secondary">
                Payment Method
              </Typography>
              <Typography variant="body1">
                {order.payment_method?.replace('_', ' ') || 'Not specified'}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="body2" color="text.secondary">
                Payment Status
              </Typography>
              <Box mt={0.5}>
                <PaymentStatusChip status={order.payment_status} />
              </Box>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="body2" color="text.secondary">
                Total Amount
              </Typography>
              <Typography variant="h6">
                {formatCurrency(order.total)}
              </Typography>
            </Grid>
          </Grid>

          {/* Refund Section */}
          {order.payment_status === 'paid' && order.status !== 'refunded' && (
            <>
              <Divider sx={{ my: 3 }} />
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Process Refund
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <TextField
                    label="Refund Amount"
                    type="number"
                    value={refundAmount}
                    onChange={(e) => setRefundAmount(e.target.value)}
                    fullWidth
                    size="small"
                    InputProps={{
                      startAdornment: '$'
                    }}
                    helperText={`Maximum: ${formatCurrency(order.total)}`}
                  />
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    label="Refund Reason"
                    multiline
                    rows={2}
                    value={refundReason}
                    onChange={(e) => setRefundReason(e.target.value)}
                    fullWidth
                    size="small"
                  />
                </Grid>
                <Grid item xs={12}>
                  <Button
                    variant="contained"
                    color="error"
                    onClick={handleRefund}
                    disabled={loading || !refundAmount}
                  >
                    Process Refund
                  </Button>
                </Grid>
              </Grid>
            </>
          )}
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          {/* Order History */}
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Order Timeline
          </Typography>
          <List>
            <ListItem>
              <ListItemText
                primary="Order Created"
                secondary={format(new Date(order.created_at), 'MMM dd, yyyy HH:mm:ss')}
              />
            </ListItem>
            {order.confirmed_at && (
              <ListItem>
                <ListItemText
                  primary="Order Confirmed"
                  secondary={format(new Date(order.confirmed_at), 'MMM dd, yyyy HH:mm:ss')}
                />
              </ListItem>
            )}
            {order.prepared_at && (
              <ListItem>
                <ListItemText
                  primary="Order Prepared"
                  secondary={format(new Date(order.prepared_at), 'MMM dd, yyyy HH:mm:ss')}
                />
              </ListItem>
            )}
            {order.delivered_at && (
              <ListItem>
                <ListItemText
                  primary="Order Delivered"
                  secondary={format(new Date(order.delivered_at), 'MMM dd, yyyy HH:mm:ss')}
                />
              </ListItem>
            )}
            {order.cancelled_at && (
              <ListItem>
                <ListItemText
                  primary="Order Cancelled"
                  secondary={format(new Date(order.cancelled_at), 'MMM dd, yyyy HH:mm:ss')}
                />
              </ListItem>
            )}
            <ListItem>
              <ListItemText
                primary="Last Updated"
                secondary={format(new Date(order.updated_at), 'MMM dd, yyyy HH:mm:ss')}
              />
            </ListItem>
          </List>
        </TabPanel>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default OrderDetails;