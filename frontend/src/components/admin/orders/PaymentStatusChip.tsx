import React from 'react';
import { Chip } from '@mui/material';
import {
  HourglassEmpty,
  CheckCircle,
  Error,
  Undo
} from '@mui/icons-material';
import { PaymentStatus } from '@/types/order.types';

interface PaymentStatusChipProps {
  status: PaymentStatus;
}

const statusConfig = {
  [PaymentStatus.PENDING]: {
    label: 'Pending',
    color: 'warning' as const,
    icon: <HourglassEmpty fontSize="small" />
  },
  [PaymentStatus.PAID]: {
    label: 'Paid',
    color: 'success' as const,
    icon: <CheckCircle fontSize="small" />
  },
  [PaymentStatus.FAILED]: {
    label: 'Failed',
    color: 'error' as const,
    icon: <Error fontSize="small" />
  },
  [PaymentStatus.REFUNDED]: {
    label: 'Refunded',
    color: 'default' as const,
    icon: <Undo fontSize="small" />
  }
};

const PaymentStatusChip: React.FC<PaymentStatusChipProps> = ({ status }) => {
  const config = statusConfig[status];
  
  return (
    <Chip
      label={config.label}
      color={config.color}
      size="small"
      icon={config.icon}
      sx={{ fontWeight: 'medium' }}
    />
  );
};

export default PaymentStatusChip;