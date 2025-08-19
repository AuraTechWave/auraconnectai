import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import OrdersScreen from '../screens/orders/OrdersScreen';
import OrderDetailsScreen from '../screens/orders/OrderDetailsScreen';
import CreateOrderScreen from '../screens/orders/CreateOrderScreen';
import OfflineOrdersScreen from '../screens/orders/OfflineOrdersScreen';
import { colors } from '../constants/designSystem';

export type OrdersStackParamList = {
  OrdersList: undefined;
  OrderDetails: { orderId: string };
  CreateOrder: undefined;
  OfflineOrders: undefined;
  ProcessPayment: { orderId: string };
};

const Stack = createNativeStackNavigator<OrdersStackParamList>();

export const OrdersNavigator: React.FC = () => {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: {
          backgroundColor: colors.primary[500],
        },
        headerTintColor: colors.text.inverse,
        headerTitleStyle: {
          fontWeight: '600',
        },
      }}
    >
      <Stack.Screen
        name="OrdersList"
        component={OrdersScreen}
        options={{ 
          title: 'Orders',
          headerShown: false,
        }}
      />
      <Stack.Screen
        name="OrderDetails"
        component={OrderDetailsScreen}
        options={{ 
          title: 'Order Details',
          headerBackTitle: 'Orders',
        }}
      />
      <Stack.Screen
        name="CreateOrder"
        component={CreateOrderScreen}
        options={{ 
          title: 'New Order',
          presentation: 'modal',
        }}
      />
      <Stack.Screen
        name="OfflineOrders"
        component={OfflineOrdersScreen}
        options={{ 
          title: 'Offline Orders',
        }}
      />
    </Stack.Navigator>
  );
};
