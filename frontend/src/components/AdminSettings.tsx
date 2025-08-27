import React from 'react';
import { Container, Typography, Box, Paper, List, ListItem, ListItemText, Switch } from '@mui/material';

const AdminSettings: React.FC = () => {
  const [settings, setSettings] = React.useState({
    emailNotifications: true,
    pushNotifications: false,
    autoAcceptOrders: false,
    darkMode: false,
  });

  const handleToggle = (setting: keyof typeof settings) => {
    setSettings(prev => ({
      ...prev,
      [setting]: !prev[setting],
    }));
  };

  return (
    <Container maxWidth="md" sx={{ py: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Admin Settings
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Configure your admin preferences and notification settings
        </Typography>
      </Box>

      <Paper elevation={1}>
        <List>
          <ListItem>
            <ListItemText 
              primary="Email Notifications"
              secondary="Receive email alerts for new orders"
            />
            <Switch
              checked={settings.emailNotifications}
              onChange={() => handleToggle('emailNotifications')}
            />
          </ListItem>
          <ListItem>
            <ListItemText 
              primary="Push Notifications"
              secondary="Receive browser push notifications"
            />
            <Switch
              checked={settings.pushNotifications}
              onChange={() => handleToggle('pushNotifications')}
            />
          </ListItem>
          <ListItem>
            <ListItemText 
              primary="Auto-Accept Orders"
              secondary="Automatically accept new orders"
            />
            <Switch
              checked={settings.autoAcceptOrders}
              onChange={() => handleToggle('autoAcceptOrders')}
            />
          </ListItem>
          <ListItem>
            <ListItemText 
              primary="Dark Mode"
              secondary="Use dark theme for the interface"
            />
            <Switch
              checked={settings.darkMode}
              onChange={() => handleToggle('darkMode')}
            />
          </ListItem>
        </List>
      </Paper>
    </Container>
  );
};

export default AdminSettings;