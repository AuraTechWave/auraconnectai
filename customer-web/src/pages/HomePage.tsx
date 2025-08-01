import React from 'react';
import { Link } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Grid,
  Card,
  CardContent,
  CardMedia,
  Container,
} from '@mui/material';
import {
  Restaurant as RestaurantIcon,
  MenuBook as MenuBookIcon,
  EventSeat as EventSeatIcon,
  Delivery as DeliveryIcon,
} from '@mui/icons-material';

export const HomePage: React.FC = () => {
  return (
    <Box>
      {/* Hero Section */}
      <Box
        sx={{
          background: 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)',
          color: 'white',
          py: 8,
          mb: 6,
        }}
      >
        <Container maxWidth="lg">
          <Grid container spacing={4} alignItems="center">
            <Grid item xs={12} md={6}>
              <Typography variant="h2" fontWeight="bold" gutterBottom>
                Welcome to AuraConnect
              </Typography>
              <Typography variant="h5" paragraph>
                Experience fine dining with our carefully crafted menu and exceptional service
              </Typography>
              <Box sx={{ mt: 4, display: 'flex', gap: 2 }}>
                <Button
                  variant="contained"
                  size="large"
                  component={Link}
                  to="/menu"
                  sx={{ bgcolor: 'white', color: 'primary.main' }}
                >
                  Order Now
                </Button>
                <Button
                  variant="outlined"
                  size="large"
                  component={Link}
                  to="/reservations/new"
                  sx={{ borderColor: 'white', color: 'white' }}
                >
                  Make Reservation
                </Button>
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box
                component="img"
                src="https://images.unsplash.com/photo-1514933651103-005eec06c04b?w=800"
                alt="Restaurant"
                sx={{
                  width: '100%',
                  borderRadius: 2,
                  boxShadow: 3,
                }}
              />
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* Features Section */}
      <Container maxWidth="lg">
        <Typography variant="h3" align="center" gutterBottom>
          Why Choose Us
        </Typography>
        <Typography variant="h6" align="center" color="text.secondary" paragraph>
          Discover what makes AuraConnect special
        </Typography>

        <Grid container spacing={4} sx={{ mt: 4 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ height: '100%', textAlign: 'center' }}>
              <CardContent>
                <MenuBookIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
                <Typography variant="h6" gutterBottom>
                  Diverse Menu
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  From classic favorites to innovative dishes, our menu offers something for everyone
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ height: '100%', textAlign: 'center' }}>
              <CardContent>
                <EventSeatIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
                <Typography variant="h6" gutterBottom>
                  Easy Reservations
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Book your table in seconds and enjoy a guaranteed spot at your preferred time
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ height: '100%', textAlign: 'center' }}>
              <CardContent>
                <DeliveryIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
                <Typography variant="h6" gutterBottom>
                  Quick Service
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Order online and track your order in real-time for pickup or dine-in
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ height: '100%', textAlign: 'center' }}>
              <CardContent>
                <RestaurantIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
                <Typography variant="h6" gutterBottom>
                  Quality Food
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Fresh ingredients and expert preparation ensure every meal is memorable
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Popular Items Section */}
        <Box sx={{ mt: 8, mb: 8 }}>
          <Typography variant="h3" align="center" gutterBottom>
            Popular Dishes
          </Typography>
          <Typography variant="h6" align="center" color="text.secondary" paragraph>
            Try our customer favorites
          </Typography>

          <Grid container spacing={4} sx={{ mt: 2 }}>
            {[1, 2, 3].map((item) => (
              <Grid item xs={12} md={4} key={item}>
                <Card>
                  <CardMedia
                    component="img"
                    height="200"
                    image={`https://images.unsplash.com/photo-${
                      item === 1
                        ? '1546069901-ba9599a7e63c'
                        : item === 2
                        ? '1567620905732-2c418291e1cd'
                        : '1565299624946-b28f40a0ae38'
                    }?w=400`}
                    alt={`Dish ${item}`}
                  />
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      {item === 1
                        ? 'Grilled Salmon'
                        : item === 2
                        ? 'Beef Tenderloin'
                        : 'Margherita Pizza'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {item === 1
                        ? 'Fresh Atlantic salmon with seasonal vegetables'
                        : item === 2
                        ? 'Premium cut beef with red wine reduction'
                        : 'Classic Italian pizza with fresh mozzarella'}
                    </Typography>
                    <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="h6" color="primary">
                        ${item === 1 ? '24.99' : item === 2 ? '34.99' : '18.99'}
                      </Typography>
                      <Button variant="outlined" size="small" component={Link} to="/menu">
                        Order Now
                      </Button>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>

        {/* CTA Section */}
        <Box
          sx={{
            bgcolor: 'grey.100',
            borderRadius: 2,
            p: 6,
            mb: 6,
            textAlign: 'center',
          }}
        >
          <Typography variant="h4" gutterBottom>
            Ready to Experience Great Food?
          </Typography>
          <Typography variant="h6" color="text.secondary" paragraph>
            Join thousands of satisfied customers who order from us every day
          </Typography>
          <Box sx={{ mt: 4, display: 'flex', gap: 2, justifyContent: 'center' }}>
            <Button variant="contained" size="large" component={Link} to="/register">
              Create Account
            </Button>
            <Button variant="outlined" size="large" component={Link} to="/menu">
              Browse Menu
            </Button>
          </Box>
        </Box>
      </Container>
    </Box>
  );
};