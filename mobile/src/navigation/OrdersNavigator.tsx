import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { View, Text } from 'react-native';

// Placeholder screens - to be implemented
const OrdersListScreen = () => (
  <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
    <Text>Orders List</Text>
  </View>
);

const OrderDetailsScreen = () => (
  <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
    <Text>Order Details</Text>
  </View>
);

export type OrdersStackParamList = {
  OrdersList: undefined;
  OrderDetails: { orderId: number };
};

const Stack = createNativeStackNavigator<OrdersStackParamList>();

export const OrdersNavigator: React.FC = () => {
  return (
    <Stack.Navigator>
      <Stack.Screen
        name="OrdersList"
        component={OrdersListScreen}
        options={{ title: 'Orders' }}
      />
      <Stack.Screen
        name="OrderDetails"
        component={OrderDetailsScreen}
        options={{ title: 'Order Details' }}
      />
    </Stack.Navigator>
  );
};