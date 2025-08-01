import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import {
  Box,
  Container,
  Typography,
  Paper,
  TextField,
  Button,
  MenuItem,
  Alert,
  Stepper,
  Step,
  StepLabel,
  FormControl,
  InputLabel,
  Select,
} from '@mui/material';
import { Grid2 as Grid } from '../components/common/Grid2';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format, addDays, setHours, setMinutes } from 'date-fns';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

interface ReservationFormData {
  date: Date;
  time: Date;
  party_size: number;
  special_requests?: string;
  table_preference?: string;
}

const steps = ['Select Date & Time', 'Guest Details', 'Confirm Reservation'];

export const ReservationPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, customer } = useAuthStore();
  const [activeStep, setActiveStep] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ReservationFormData>({
    defaultValues: {
      date: addDays(new Date(), 1),
      time: setHours(setMinutes(new Date(), 0), 19), // Default 7:00 PM
      party_size: 2,
      special_requests: '',
      table_preference: 'no_preference',
    },
  });

  const watchedDate = watch('date');
  const watchedTime = watch('time');

  const handleNext = () => {
    setActiveStep((prevStep) => prevStep + 1);
  };

  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };

  const onSubmit = async (data: ReservationFormData) => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: '/reservations/new' } });
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const reservationData = {
        date: format(data.date, 'yyyy-MM-dd'),
        time: format(data.time, 'HH:mm'),
        party_size: data.party_size,
        special_requests: data.special_requests,
        table_preference: data.table_preference,
      };

      await api.createReservation(reservationData);
      navigate('/reservations', { state: { success: true } });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create reservation');
    } finally {
      setIsSubmitting(false);
    }
  };

  const getStepContent = (step: number) => {
    switch (step) {
      case 0:
        return (
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Controller
                name="date"
                control={control}
                rules={{ required: 'Date is required' }}
                render={({ field }) => (
                  <LocalizationProvider dateAdapter={AdapterDateFns}>
                    <DatePicker
                      label="Reservation Date"
                      value={field.value}
                      onChange={field.onChange}
                      minDate={addDays(new Date(), 1)}
                      maxDate={addDays(new Date(), 60)}
                      slotProps={{
                        textField: {
                          fullWidth: true,
                          error: !!errors.date,
                          helperText: errors.date?.message,
                        },
                      }}
                    />
                  </LocalizationProvider>
                )}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <Controller
                name="time"
                control={control}
                rules={{ required: 'Time is required' }}
                render={({ field }) => (
                  <LocalizationProvider dateAdapter={AdapterDateFns}>
                    <TimePicker
                      label="Reservation Time"
                      value={field.value}
                      onChange={field.onChange}
                      minTime={setHours(setMinutes(new Date(), 0), 11)}
                      maxTime={setHours(setMinutes(new Date(), 0), 21)}
                      slotProps={{
                        textField: {
                          fullWidth: true,
                          error: !!errors.time,
                          helperText: errors.time?.message,
                        },
                      }}
                    />
                  </LocalizationProvider>
                )}
              />
            </Grid>
            <Grid item xs={12}>
              <Controller
                name="party_size"
                control={control}
                rules={{ required: 'Party size is required' }}
                render={({ field }) => (
                  <TextField
                    select
                    fullWidth
                    label="Party Size"
                    {...field}
                    error={!!errors.party_size}
                    helperText={errors.party_size?.message}
                  >
                    {[1, 2, 3, 4, 5, 6, 7, 8].map((size) => (
                      <MenuItem key={size} value={size}>
                        {size} {size === 1 ? 'Guest' : 'Guests'}
                      </MenuItem>
                    ))}
                  </TextField>
                )}
              />
            </Grid>
          </Grid>
        );

      case 1:
        return (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Controller
                name="table_preference"
                control={control}
                render={({ field }) => (
                  <TextField
                    select
                    fullWidth
                    label="Table Preference"
                    {...field}
                  >
                    <MenuItem value="no_preference">No Preference</MenuItem>
                    <MenuItem value="window">Window Seat</MenuItem>
                    <MenuItem value="booth">Booth</MenuItem>
                    <MenuItem value="patio">Patio</MenuItem>
                    <MenuItem value="private">Private Dining</MenuItem>
                  </TextField>
                )}
              />
            </Grid>
            <Grid item xs={12}>
              <Controller
                name="special_requests"
                control={control}
                render={({ field }) => (
                  <TextField
                    fullWidth
                    multiline
                    rows={4}
                    label="Special Requests (Optional)"
                    placeholder="e.g., Birthday celebration, dietary restrictions, wheelchair accessible"
                    {...field}
                  />
                )}
              />
            </Grid>
            {!isAuthenticated && (
              <Grid item xs={12}>
                <Alert severity="info">
                  Please login or create an account to complete your reservation
                </Alert>
              </Grid>
            )}
          </Grid>
        );

      case 2:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Confirm Your Reservation
            </Typography>
            <Paper sx={{ p: 3, bgcolor: 'grey.50' }}>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Date
                  </Typography>
                  <Typography variant="body1">
                    {format(watchedDate, 'EEEE, MMMM d, yyyy')}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Time
                  </Typography>
                  <Typography variant="body1">
                    {format(watchedTime, 'h:mm a')}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Party Size
                  </Typography>
                  <Typography variant="body1">
                    {watch('party_size')} {watch('party_size') === 1 ? 'Guest' : 'Guests'}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Table Preference
                  </Typography>
                  <Typography variant="body1">
                    {watch('table_preference')?.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </Typography>
                </Grid>
                {watch('special_requests') && (
                  <Grid item xs={12}>
                    <Typography variant="body2" color="text.secondary">
                      Special Requests
                    </Typography>
                    <Typography variant="body1">
                      {watch('special_requests')}
                    </Typography>
                  </Grid>
                )}
              </Grid>
            </Paper>
            {customer && (
              <Box sx={{ mt: 3 }}>
                <Typography variant="body2" color="text.secondary">
                  Reservation will be made for:
                </Typography>
                <Typography variant="body1">
                  {customer.first_name} {customer.last_name} ({customer.email})
                </Typography>
              </Box>
            )}
          </Box>
        );

      default:
        return null;
    }
  };

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom>
        Make a Reservation
      </Typography>
      
      <Paper sx={{ p: 4, mt: 3 }}>
        <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        <form onSubmit={handleSubmit(onSubmit)}>
          {getStepContent(activeStep)}

          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
            <Button
              disabled={activeStep === 0}
              onClick={handleBack}
            >
              Back
            </Button>
            {activeStep === steps.length - 1 ? (
              <Button
                variant="contained"
                type="submit"
                disabled={isSubmitting || !isAuthenticated}
              >
                {isSubmitting ? 'Creating...' : 'Confirm Reservation'}
              </Button>
            ) : (
              <Button variant="contained" onClick={handleNext}>
                Next
              </Button>
            )}
          </Box>
        </form>
      </Paper>
    </Container>
  );
};