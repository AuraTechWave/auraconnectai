import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import BulkOperations from '../BulkOperations';

const mockProps = {
  selectedItems: [1, 2, 3],
  onSelectAll: jest.fn(),
  onDeselectAll: jest.fn(),
  onBulkDelete: jest.fn(),
  onBulkActivate: jest.fn(),
  onBulkDeactivate: jest.fn(),
  onBulkAssignRole: jest.fn(),
  totalItems: 10,
  itemType: 'users' as const,
  availableRoles: [
    { id: 1, name: 'admin', display_name: 'Administrator' },
    { id: 2, name: 'manager', display_name: 'Manager' }
  ]
};

describe('BulkOperations', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders bulk operations when items are selected', () => {
    render(<BulkOperations {...mockProps} />);

    expect(screen.getByText('3 of 10 users selected')).toBeInTheDocument();
    expect(screen.getByText('Select All')).toBeInTheDocument();
    expect(screen.getByText('Activate Selected')).toBeInTheDocument();
    expect(screen.getByText('Deactivate Selected')).toBeInTheDocument();
    expect(screen.getByText('Delete Selected')).toBeInTheDocument();
    expect(screen.getByText('Assign Role')).toBeInTheDocument();
  });

  it('does not render when no items are selected', () => {
    render(<BulkOperations {...mockProps} selectedItems={[]} />);

    expect(screen.queryByText('0 of 10 users selected')).not.toBeInTheDocument();
  });

  it('shows "Deselect All" when all items are selected', () => {
    render(
      <BulkOperations 
        {...mockProps} 
        selectedItems={[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}
      />
    );

    expect(screen.getByText('Deselect All')).toBeInTheDocument();
  });

  it('calls onSelectAll when Select All is clicked', () => {
    render(<BulkOperations {...mockProps} />);

    fireEvent.click(screen.getByText('Select All'));
    expect(mockProps.onSelectAll).toHaveBeenCalledTimes(1);
  });

  it('calls onDeselectAll when Deselect All is clicked', () => {
    render(
      <BulkOperations 
        {...mockProps} 
        selectedItems={[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}
      />
    );

    fireEvent.click(screen.getByText('Deselect All'));
    expect(mockProps.onDeselectAll).toHaveBeenCalledTimes(1);
  });

  it('calls onBulkActivate when Activate Selected is clicked', () => {
    render(<BulkOperations {...mockProps} />);

    fireEvent.click(screen.getByText('Activate Selected'));
    expect(mockProps.onBulkActivate).toHaveBeenCalledTimes(1);
  });

  it('calls onBulkDeactivate when Deactivate Selected is clicked', () => {
    render(<BulkOperations {...mockProps} />);

    fireEvent.click(screen.getByText('Deactivate Selected'));
    expect(mockProps.onBulkDeactivate).toHaveBeenCalledTimes(1);
  });

  it('calls onBulkDelete when Delete Selected is clicked', () => {
    render(<BulkOperations {...mockProps} />);

    fireEvent.click(screen.getByText('Delete Selected'));
    expect(mockProps.onBulkDelete).toHaveBeenCalledTimes(1);
  });

  it('shows role selector when Assign Role is clicked', () => {
    render(<BulkOperations {...mockProps} />);

    fireEvent.click(screen.getByText('Assign Role'));

    expect(screen.getByDisplayValue('')).toBeInTheDocument();
    expect(screen.getByText('Administrator')).toBeInTheDocument();
    expect(screen.getByText('Manager')).toBeInTheDocument();
    expect(screen.getByText('Assign')).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();
  });

  it('assigns role when role is selected and Assign is clicked', () => {
    render(<BulkOperations {...mockProps} />);

    // Open role selector
    fireEvent.click(screen.getByText('Assign Role'));

    // Select a role
    const select = screen.getByDisplayValue('');
    fireEvent.change(select, { target: { value: '1' } });

    // Click assign
    fireEvent.click(screen.getByText('Assign'));

    expect(mockProps.onBulkAssignRole).toHaveBeenCalledWith(1);
  });

  it('cancels role assignment when Cancel is clicked', () => {
    render(<BulkOperations {...mockProps} />);

    // Open role selector
    fireEvent.click(screen.getByText('Assign Role'));

    // Cancel
    fireEvent.click(screen.getByText('Cancel'));

    // Should go back to initial state
    expect(screen.getByText('Assign Role')).toBeInTheDocument();
    expect(screen.queryByText('Assign')).not.toBeInTheDocument();
  });

  it('disables Assign button when no role is selected', () => {
    render(<BulkOperations {...mockProps} />);

    fireEvent.click(screen.getByText('Assign Role'));

    const assignButton = screen.getByText('Assign');
    expect(assignButton).toBeDisabled();
  });

  it('enables Assign button when role is selected', () => {
    render(<BulkOperations {...mockProps} />);

    fireEvent.click(screen.getByText('Assign Role'));

    const select = screen.getByDisplayValue('');
    fireEvent.change(select, { target: { value: '1' } });

    const assignButton = screen.getByText('Assign');
    expect(assignButton).not.toBeDisabled();
  });

  it('does not show role assignment when no roles are available', () => {
    render(<BulkOperations {...mockProps} availableRoles={[]} />);

    expect(screen.queryByText('Assign Role')).not.toBeInTheDocument();
  });

  it('does not show optional actions when callbacks are not provided', () => {
    const minimalProps = {
      selectedItems: [1, 2],
      onSelectAll: jest.fn(),
      onDeselectAll: jest.fn(),
      totalItems: 10,
      itemType: 'users' as const
    };

    render(<BulkOperations {...minimalProps} />);

    expect(screen.queryByText('Activate Selected')).not.toBeInTheDocument();
    expect(screen.queryByText('Deactivate Selected')).not.toBeInTheDocument();
    expect(screen.queryByText('Delete Selected')).not.toBeInTheDocument();
    expect(screen.queryByText('Assign Role')).not.toBeInTheDocument();
  });

  it('displays correct item type in selection count', () => {
    render(<BulkOperations {...mockProps} itemType="roles" />);

    expect(screen.getByText('3 of 10 roles selected')).toBeInTheDocument();
  });

  it('resets role selector state after successful assignment', () => {
    render(<BulkOperations {...mockProps} />);

    // Open role selector
    fireEvent.click(screen.getByText('Assign Role'));

    // Select a role
    const select = screen.getByDisplayValue('');
    fireEvent.change(select, { target: { value: '1' } });

    // Click assign
    fireEvent.click(screen.getByText('Assign'));

    // Role selector should be hidden and reset
    expect(screen.getByText('Assign Role')).toBeInTheDocument();
    expect(screen.queryByText('Assign')).not.toBeInTheDocument();
  });

  it('applies correct CSS classes', () => {
    const { container } = render(<BulkOperations {...mockProps} />);

    expect(container.firstChild).toHaveClass('bulk-operations');
    expect(screen.getByText('3 of 10 users selected')).toHaveClass('selected-count');
    
    const actionsContainer = screen.getByText('Select All').parentElement;
    expect(actionsContainer).toHaveClass('bulk-actions');
  });
});