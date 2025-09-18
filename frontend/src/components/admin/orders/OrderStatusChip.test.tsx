import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { OrderStatusChip } from './OrderStatusChip';
import { OrderStatus } from '../../../types/order.types';

describe('OrderStatusChip', () => {
  describe('Display', () => {
    test('renders pending status correctly', () => {
      render(<OrderStatusChip status={OrderStatus.PENDING} />);
      expect(screen.getByText('Pending')).toBeInTheDocument();
    });

    test('renders confirmed status correctly', () => {
      render(<OrderStatusChip status={OrderStatus.CONFIRMED} />);
      expect(screen.getByText('Confirmed')).toBeInTheDocument();
    });

    test('renders in progress status correctly', () => {
      render(<OrderStatusChip status={OrderStatus.IN_PROGRESS} />);
      expect(screen.getByText('In Progress')).toBeInTheDocument();
    });

    test('renders preparing status correctly', () => {
      render(<OrderStatusChip status={OrderStatus.PREPARING} />);
      expect(screen.getByText('Preparing')).toBeInTheDocument();
    });

    test('renders ready status correctly', () => {
      render(<OrderStatusChip status={OrderStatus.READY} />);
      expect(screen.getByText('Ready')).toBeInTheDocument();
    });

    test('renders completed status correctly', () => {
      render(<OrderStatusChip status={OrderStatus.COMPLETED} />);
      expect(screen.getByText('Completed')).toBeInTheDocument();
    });

    test('renders delivered status correctly', () => {
      render(<OrderStatusChip status={OrderStatus.DELIVERED} />);
      expect(screen.getByText('Delivered')).toBeInTheDocument();
    });

    test('renders cancelled status correctly', () => {
      render(<OrderStatusChip status={OrderStatus.CANCELLED} />);
      expect(screen.getByText('Cancelled')).toBeInTheDocument();
    });
  });

  describe('Interaction', () => {
    test('shows menu when clicked in editable mode', async () => {
      const handleChange = jest.fn();
      render(
        <OrderStatusChip 
          status={OrderStatus.PENDING} 
          onChange={handleChange}
          readOnly={false}
        />
      );
      
      const chip = screen.getByText('Pending');
      fireEvent.click(chip);
      
      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });
    });

    test('does not show menu when clicked in readonly mode', () => {
      render(
        <OrderStatusChip 
          status={OrderStatus.PENDING} 
          readOnly={true}
        />
      );
      
      const chip = screen.getByText('Pending');
      fireEvent.click(chip);
      
      expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    });

    test('calls onChange when status is selected from menu', async () => {
      const handleChange = jest.fn();
      render(
        <OrderStatusChip 
          status={OrderStatus.PENDING} 
          onChange={handleChange}
          readOnly={false}
        />
      );
      
      const chip = screen.getByText('Pending');
      fireEvent.click(chip);
      
      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });
      
      const confirmedOption = screen.getByText('Confirmed');
      fireEvent.click(confirmedOption);
      
      expect(handleChange).toHaveBeenCalledWith(OrderStatus.CONFIRMED);
    });

    test('closes menu after status selection', async () => {
      const handleChange = jest.fn();
      render(
        <OrderStatusChip 
          status={OrderStatus.PENDING} 
          onChange={handleChange}
          readOnly={false}
        />
      );
      
      const chip = screen.getByText('Pending');
      fireEvent.click(chip);
      
      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });
      
      const confirmedOption = screen.getByText('Confirmed');
      fireEvent.click(confirmedOption);
      
      await waitFor(() => {
        expect(screen.queryByRole('menu')).not.toBeInTheDocument();
      });
    });
  });

  describe('Styling', () => {
    test('applies correct color for pending status', () => {
      const { container } = render(<OrderStatusChip status={OrderStatus.PENDING} />);
      const chip = container.querySelector('.MuiChip-colorWarning');
      expect(chip).toBeInTheDocument();
    });

    test('applies correct color for confirmed status', () => {
      const { container } = render(<OrderStatusChip status={OrderStatus.CONFIRMED} />);
      const chip = container.querySelector('.MuiChip-colorInfo');
      expect(chip).toBeInTheDocument();
    });

    test('applies correct color for ready status', () => {
      const { container } = render(<OrderStatusChip status={OrderStatus.READY} />);
      const chip = container.querySelector('.MuiChip-colorSuccess');
      expect(chip).toBeInTheDocument();
    });

    test('applies correct color for cancelled status', () => {
      const { container } = render(<OrderStatusChip status={OrderStatus.CANCELLED} />);
      const chip = container.querySelector('.MuiChip-colorError');
      expect(chip).toBeInTheDocument();
    });
  });
});