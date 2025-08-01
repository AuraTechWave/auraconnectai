import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  IconButton,
  Badge,
  Menu,
  MenuItem,
  Box,
  Container,
} from '@mui/material';
import {
  ShoppingCart as ShoppingCartIcon,
  AccountCircle as AccountCircleIcon,
  Restaurant as RestaurantIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../../store/authStore';
import { useCartStore } from '../../store/cartStore';

export const Header: React.FC = () => {
  const navigate = useNavigate();
  const { customer, isAuthenticated, logout } = useAuthStore();
  const { getItemCount } = useCartStore();
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

  const itemCount = getItemCount();

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = async () => {
    await logout();
    handleMenuClose();
    navigate('/');
  };

  const handleProfile = () => {
    handleMenuClose();
    navigate('/profile');
  };

  const handleOrders = () => {
    handleMenuClose();
    navigate('/orders');
  };

  const handleReservations = () => {
    handleMenuClose();
    navigate('/reservations');
  };

  return (
    <AppBar position="sticky" color="primary">
      <Container maxWidth="lg">
        <Toolbar>
          <RestaurantIcon sx={{ mr: 2 }} />
          <Typography
            variant="h6"
            component={Link}
            to="/"
            sx={{
              flexGrow: 1,
              textDecoration: 'none',
              color: 'inherit',
              fontWeight: 'bold',
            }}
          >
            AuraConnect Restaurant
          </Typography>

          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <Button
              color="inherit"
              component={Link}
              to="/menu"
              sx={{ display: { xs: 'none', sm: 'block' } }}
            >
              Menu
            </Button>

            <Button
              color="inherit"
              component={Link}
              to="/reservations/new"
              sx={{ display: { xs: 'none', sm: 'block' } }}
            >
              Reserve Table
            </Button>

            <IconButton
              color="inherit"
              component={Link}
              to="/cart"
              aria-label="shopping cart"
            >
              <Badge badgeContent={itemCount} color="secondary">
                <ShoppingCartIcon />
              </Badge>
            </IconButton>

            {isAuthenticated ? (
              <>
                <IconButton
                  color="inherit"
                  onClick={handleMenuOpen}
                  aria-label="account menu"
                >
                  <AccountCircleIcon />
                </IconButton>
                <Menu
                  anchorEl={anchorEl}
                  open={Boolean(anchorEl)}
                  onClose={handleMenuClose}
                  anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'right',
                  }}
                  transformOrigin={{
                    vertical: 'top',
                    horizontal: 'right',
                  }}
                >
                  <MenuItem disabled>
                    <Typography variant="body2" color="text.secondary">
                      {customer?.email}
                    </Typography>
                  </MenuItem>
                  <MenuItem onClick={handleProfile}>My Profile</MenuItem>
                  <MenuItem onClick={handleOrders}>My Orders</MenuItem>
                  <MenuItem onClick={handleReservations}>My Reservations</MenuItem>
                  <MenuItem onClick={handleLogout}>Logout</MenuItem>
                </Menu>
              </>
            ) : (
              <Button
                color="inherit"
                component={Link}
                to="/login"
                variant="outlined"
                sx={{ borderColor: 'rgba(255, 255, 255, 0.5)' }}
              >
                Login
              </Button>
            )}
          </Box>
        </Toolbar>
      </Container>
    </AppBar>
  );
};