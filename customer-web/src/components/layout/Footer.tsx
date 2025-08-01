import React from 'react';
import { Box, Container, Typography, Link, Grid } from '@mui/material';

export const Footer: React.FC = () => {
  return (
    <Box
      component="footer"
      sx={{
        py: 3,
        px: 2,
        mt: 'auto',
        backgroundColor: (theme) =>
          theme.palette.mode === 'light'
            ? theme.palette.grey[200]
            : theme.palette.grey[800],
      }}
    >
      <Container maxWidth="lg">
        <Grid container spacing={4}>
          <Grid item xs={12} sm={4}>
            <Typography variant="h6" color="text.primary" gutterBottom>
              AuraConnect Restaurant
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Experience fine dining with our carefully crafted menu and exceptional service.
            </Typography>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Typography variant="h6" color="text.primary" gutterBottom>
              Contact
            </Typography>
            <Typography variant="body2" color="text.secondary">
              123 Restaurant Street
              <br />
              City, State 12345
              <br />
              Phone: (555) 123-4567
              <br />
              Email: info@auraconnect.com
            </Typography>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Typography variant="h6" color="text.primary" gutterBottom>
              Hours
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Monday - Thursday: 11:00 AM - 10:00 PM
              <br />
              Friday - Saturday: 11:00 AM - 11:00 PM
              <br />
              Sunday: 10:00 AM - 9:00 PM
            </Typography>
          </Grid>
        </Grid>
        <Box mt={3}>
          <Typography variant="body2" color="text.secondary" align="center">
            {'© '}
            {new Date().getFullYear()}
            {' AuraConnect. All rights reserved.'}
          </Typography>
        </Box>
      </Container>
    </Box>
  );
};