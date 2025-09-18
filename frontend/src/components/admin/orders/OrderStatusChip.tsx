import React, { useState } from 'react';
import {
  Chip,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText
} from '@mui/material';
import {
  HourglassEmpty,
  CheckCircle,
  Restaurant,
  Done,
  LocalShipping,
  Cancel,
  Undo
} from '@mui/icons-material';
import { OrderStatus } from '../../../types/order.types';

interface OrderStatusChipProps {
  status: OrderStatus;
  onChange?: (newStatus: OrderStatus) => void;
  readOnly?: boolean;
}

const statusConfig = {
  [OrderStatus.PENDING]: {
    label: 'Pending',
    color: 'warning' as const,
    icon: <HourglassEmpty fontSize="small" />
  },
  [OrderStatus.CONFIRMED]: {
    label: 'Confirmed',
    color: 'info' as const,
    icon: <CheckCircle fontSize="small" />
  },
  [OrderStatus.IN_PROGRESS]: {
    label: 'In Progress',
    color: 'primary' as const,
    icon: <Restaurant fontSize="small" />
  },
  [OrderStatus.PREPARING]: {
    label: 'Preparing',
    color: 'primary' as const,
    icon: <Restaurant fontSize="small" />
  },
  [OrderStatus.READY]: {
    label: 'Ready',
    color: 'success' as const,
    icon: <Done fontSize="small" />
  },
  [OrderStatus.COMPLETED]: {
    label: 'Completed',
    color: 'success' as const,
    icon: <Done fontSize="small" />
  },
  [OrderStatus.DELIVERED]: {
    label: 'Delivered',
    color: 'default' as const,
    icon: <LocalShipping fontSize="small" />
  },
  [OrderStatus.CANCELLED]: {
    label: 'Cancelled',
    color: 'error' as const,
    icon: <Cancel fontSize="small" />
  },
  [OrderStatus.DELAYED]: {
    label: 'Delayed',
    color: 'warning' as const,
    icon: <HourglassEmpty fontSize="small" />
  },
  [OrderStatus.REFUNDED]: {
    label: 'Refunded',
    color: 'error' as const,
    icon: <Undo fontSize="small" />
  }
};

const statusTransitions: Record<OrderStatus, OrderStatus[]> = {
  [OrderStatus.PENDING]: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
  [OrderStatus.CONFIRMED]: [OrderStatus.IN_PROGRESS, OrderStatus.PREPARING, OrderStatus.CANCELLED],
  [OrderStatus.IN_PROGRESS]: [OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.CANCELLED],
  [OrderStatus.PREPARING]: [OrderStatus.READY, OrderStatus.CANCELLED],
  [OrderStatus.READY]: [OrderStatus.COMPLETED, OrderStatus.DELIVERED, OrderStatus.CANCELLED],
  [OrderStatus.COMPLETED]: [OrderStatus.REFUNDED],
  [OrderStatus.DELIVERED]: [OrderStatus.REFUNDED],
  [OrderStatus.CANCELLED]: [],
  [OrderStatus.DELAYED]: [OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.CANCELLED],
  [OrderStatus.REFUNDED]: []
};

const OrderStatusChip: React.FC<OrderStatusChipProps> = ({
  status,
  onChange,
  readOnly = false
}) => {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const config = statusConfig[status];
  const availableTransitions = statusTransitions[status];

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    if (!readOnly && onChange && availableTransitions.length > 0) {
      setAnchorEl(event.currentTarget);
    }
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleStatusChange = (newStatus: OrderStatus) => {
    if (onChange) {
      onChange(newStatus);
    }
    handleClose();
  };

  return (
    <>
      <Chip
        label={config.label}
        color={config.color}
        size="small"
        icon={config.icon}
        onClick={handleClick}
        clickable={!readOnly && availableTransitions.length > 0}
        sx={{
          fontWeight: 'medium',
          cursor: !readOnly && availableTransitions.length > 0 ? 'pointer' : 'default'
        }}
      />
      
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
      >
        {availableTransitions.map((nextStatus) => {
          const nextConfig = statusConfig[nextStatus];
          return (
            <MenuItem
              key={nextStatus}
              onClick={() => handleStatusChange(nextStatus)}
            >
              <ListItemIcon>
                {nextConfig.icon}
              </ListItemIcon>
              <ListItemText>
                Change to {nextConfig.label}
              </ListItemText>
            </MenuItem>
          );
        })}
      </Menu>
    </>
  );
};

export { OrderStatusChip };
export default OrderStatusChip;