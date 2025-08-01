import React from 'react';
import { Box, Container } from '@mui/material';
import { Header } from './Header';
import { Footer } from './Footer';
import DemoNotice from '../DemoNotice';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Header />
      <Box component="main" sx={{ flexGrow: 1, py: 4 }}>
        <Container maxWidth="lg">
          <DemoNotice />
          {children}
        </Container>
      </Box>
      <Footer />
    </Box>
  );
};