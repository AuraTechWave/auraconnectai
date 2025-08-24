import React, { useState } from 'react';
import {
  Box,
  Container,
  Tabs,
  Tab,
  Paper
} from '@mui/material';
import {
  List as ListIcon,
  Dashboard as DashboardIcon
} from '@mui/icons-material';
import OrderList from '@/components/admin/orders/OrderList';
import OrderAnalyticsDashboard from '@/components/admin/orders/OrderAnalyticsDashboard';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div hidden={value !== index}>
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
};

const OrderManagementPage: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  return (
    <Container maxWidth="xl">
      <Box sx={{ mt: 3 }}>
        <Paper sx={{ mb: 2 }}>
          <Tabs
            value={tabValue}
            onChange={handleTabChange}
            variant="fullWidth"
            indicatorColor="primary"
            textColor="primary"
          >
            <Tab
              label="Order List"
              icon={<ListIcon />}
              iconPosition="start"
            />
            <Tab
              label="Analytics Dashboard"
              icon={<DashboardIcon />}
              iconPosition="start"
            />
          </Tabs>
        </Paper>

        <TabPanel value={tabValue} index={0}>
          <OrderList />
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <OrderAnalyticsDashboard />
        </TabPanel>
      </Box>
    </Container>
  );
};

export default OrderManagementPage;