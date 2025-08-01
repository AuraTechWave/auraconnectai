import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import {
  Box,
  TextField,
  Button,
  Typography,
  Paper,
  Alert,
  CircularProgress,
  Checkbox,
  FormControlLabel,
} from '@mui/material';
import { Grid2 as Grid } from '../common/Grid2';
import {
  Email as EmailIcon,
  Lock as LockIcon,
  Person as PersonIcon,
  Phone as PhoneIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../../store/authStore';

interface RegisterFormData {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  password: string;
  confirmPassword: string;
  agreeToTerms: boolean;
}

export const RegisterForm: React.FC = () => {
  const navigate = useNavigate();
  const { register: registerUser, isLoading, error, clearError } = useAuthStore();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterFormData>();

  const password = watch('password');

  const onSubmit = async (data: RegisterFormData) => {
    const { confirmPassword, agreeToTerms, ...registerData } = data;
    try {
      await registerUser(registerData);
      navigate('/');
    } catch (error) {
      // Error is handled in the store
    }
  };

  React.useEffect(() => {
    clearError();
  }, [clearError]);

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '80vh',
        py: 4,
      }}
    >
      <Paper elevation={3} sx={{ p: 4, maxWidth: 500, width: '100%' }}>
        <Typography variant="h4" align="center" gutterBottom>
          Create Account
        </Typography>
        <Typography variant="body2" align="center" color="text.secondary" mb={3}>
          Join us to enjoy exclusive benefits and faster checkout
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <form onSubmit={handleSubmit(onSubmit)}>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="First Name"
                InputProps={{
                  startAdornment: <PersonIcon color="action" sx={{ mr: 1 }} />,
                }}
                {...register('first_name', {
                  required: 'First name is required',
                  minLength: {
                    value: 2,
                    message: 'First name must be at least 2 characters',
                  },
                })}
                error={!!errors.first_name}
                helperText={errors.first_name?.message}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Last Name"
                {...register('last_name', {
                  required: 'Last name is required',
                  minLength: {
                    value: 2,
                    message: 'Last name must be at least 2 characters',
                  },
                })}
                error={!!errors.last_name}
                helperText={errors.last_name?.message}
              />
            </Grid>
          </Grid>

          <TextField
            fullWidth
            label="Email"
            type="email"
            margin="normal"
            InputProps={{
              startAdornment: <EmailIcon color="action" sx={{ mr: 1 }} />,
            }}
            {...register('email', {
              required: 'Email is required',
              pattern: {
                value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                message: 'Invalid email address',
              },
            })}
            error={!!errors.email}
            helperText={errors.email?.message}
          />

          <TextField
            fullWidth
            label="Phone Number"
            type="tel"
            margin="normal"
            InputProps={{
              startAdornment: <PhoneIcon color="action" sx={{ mr: 1 }} />,
            }}
            {...register('phone', {
              required: 'Phone number is required',
              pattern: {
                value: /^[0-9]{10}$/,
                message: 'Phone number must be 10 digits',
              },
            })}
            error={!!errors.phone}
            helperText={errors.phone?.message}
          />

          <TextField
            fullWidth
            label="Password"
            type="password"
            margin="normal"
            InputProps={{
              startAdornment: <LockIcon color="action" sx={{ mr: 1 }} />,
            }}
            {...register('password', {
              required: 'Password is required',
              minLength: {
                value: 8,
                message: 'Password must be at least 8 characters',
              },
              pattern: {
                value: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d@$!%*?&]{8,}$/,
                message:
                  'Password must contain at least one uppercase letter, one lowercase letter, and one number',
              },
            })}
            error={!!errors.password}
            helperText={errors.password?.message}
          />

          <TextField
            fullWidth
            label="Confirm Password"
            type="password"
            margin="normal"
            {...register('confirmPassword', {
              required: 'Please confirm your password',
              validate: (value) => value === password || 'Passwords do not match',
            })}
            error={!!errors.confirmPassword}
            helperText={errors.confirmPassword?.message}
          />

          <FormControlLabel
            control={
              <Checkbox
                {...register('agreeToTerms', {
                  required: 'You must agree to the terms and conditions',
                })}
              />
            }
            label={
              <Typography variant="body2">
                I agree to the{' '}
                <Link to="/terms" style={{ color: 'primary' }}>
                  Terms and Conditions
                </Link>
              </Typography>
            }
            sx={{ mt: 2, mb: 1 }}
          />
          {errors.agreeToTerms && (
            <Typography color="error" variant="caption">
              {errors.agreeToTerms.message}
            </Typography>
          )}

          <Button
            type="submit"
            fullWidth
            variant="contained"
            size="large"
            disabled={isLoading}
            sx={{ mt: 2, mb: 2 }}
          >
            {isLoading ? <CircularProgress size={24} /> : 'Create Account'}
          </Button>

          <Typography variant="body2" align="center">
            Already have an account?{' '}
            <Link to="/login" style={{ color: 'primary', textDecoration: 'none' }}>
              Login here
            </Link>
          </Typography>
        </form>
      </Paper>
    </Box>
  );
};