import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { ReservationPage } from '../ReservationPage';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

jest.mock('../../store/authStore');
jest.mock('../../services/api');

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

describe('ReservationPage', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    jest.clearAllMocks();
    (useAuthStore as unknown as jest.Mock).mockReturnValue({
      isAuthenticated: false,
      customer: null,
    });
  });

  const renderReservationPage = () => {
    render(
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <LocalizationProvider dateAdapter={AdapterDateFns}>
            <ReservationPage />
          </LocalizationProvider>
        </QueryClientProvider>
      </BrowserRouter>
    );
  };

  test('renders reservation form', () => {
    renderReservationPage();

    expect(screen.getByText(/make a reservation/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/party size/i)).toBeInTheDocument();
  });

  test('allows guest reservations', async () => {
    renderReservationPage();

    // Fill in the form
    const partySizeSelect = screen.getByLabelText(/party size/i);
    fireEvent.mouseDown(partySizeSelect);
    
    await waitFor(() => {
      const option = screen.getByRole('option', { name: '4 guests' });
      fireEvent.click(option);
    });

    // Continue through the form
    const nextButton = screen.getByText(/next/i);
    expect(nextButton).toBeEnabled();
  });

  test('validates party size', async () => {
    renderReservationPage();

    const submitButton = screen.getByText(/next/i);
    fireEvent.click(submitButton);

    // Should show validation error for missing fields
    await waitFor(() => {
      expect(screen.getByText(/party size is required/i)).toBeInTheDocument();
    });
  });

  test('shows login prompt for authenticated features', () => {
    renderReservationPage();

    // Guest users should see guest form
    expect(screen.queryByText(/login to access/i)).not.toBeInTheDocument();
  });

  test('handles reservation submission', async () => {
    (api.createReservation as jest.Mock).mockResolvedValue({
      data: {
        id: 1,
        confirmation_code: 'ABC123',
        status: 'confirmed',
      },
    });

    renderReservationPage();

    // Fill in the form
    const partySizeSelect = screen.getByLabelText(/party size/i);
    fireEvent.mouseDown(partySizeSelect);
    
    await waitFor(() => {
      const option = screen.getByRole('option', { name: '2 guests' });
      fireEvent.click(option);
    });

    // Move to next step
    const nextButton = screen.getByText(/next/i);
    fireEvent.click(nextButton);

    // Fill guest details
    await waitFor(() => {
      const nameInput = screen.getByLabelText(/name/i);
      fireEvent.change(nameInput, { target: { value: 'John Doe' } });
    });
  });
});