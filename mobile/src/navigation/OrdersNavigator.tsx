import React, { lazy, Suspense } from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { View, ActivityIndicator } from 'react-native';
import OrdersScreen from '../screens/orders/OrdersScreen';
import { colors } from '../constants/designSystem';

// Lazy load heavy screens
const OrderDetailsScreen = lazy(() => import('../screens/orders/OrderDetailsScreen'));
const CreateOrderScreen = lazy(() => import('../screens/orders/CreateOrderScreen'));
const OfflineOrdersScreen = lazy(() => import('../screens/orders/OfflineOrdersScreen'));
const ProcessPaymentScreen = lazy(() => import('../screens/orders/ProcessPaymentScreen'));

// Loading component
const ScreenLoader = () => (
  <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
    <ActivityIndicator size="large" color={colors.primary[500]} />
  </View>
);

// Wrap lazy components
const LazyOrderDetails = (props: any) => (
  <Suspense fallback={<ScreenLoader />}>
    <OrderDetailsScreen {...props} />
  </Suspense>
);

const LazyCreateOrder = (props: any) => (
  <Suspense fallback={<ScreenLoader />}>
    <CreateOrderScreen {...props} />
  </Suspense>
);

const LazyOfflineOrders = (props: any) => (
  <Suspense fallback={<ScreenLoader />}>
    <OfflineOrdersScreen {...props} />
  </Suspense>
);

const LazyProcessPayment = (props: any) => (
  <Suspense fallback={<ScreenLoader />}>
    <ProcessPaymentScreen {...props} />
  </Suspense>
);

export type OrdersStackParamList = {
  OrdersList: undefined;
  OrderDetails: { orderId: string | number }; // Support both for backward compatibility
  CreateOrder: undefined;
  OfflineOrders: undefined;
  ProcessPayment: { orderId: string | number }; // Support both for backward compatibility
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
        component={LazyOrderDetails}
        options={{ 
          title: 'Order Details',
          headerBackTitle: 'Orders',
        }}
      />
      <Stack.Screen
        name="CreateOrder"
        component={LazyCreateOrder}
        options={{ 
          title: 'New Order',
          presentation: 'modal',
        }}
      />
      <Stack.Screen
        name="OfflineOrders"
        component={LazyOfflineOrders}
        options={{ 
          title: 'Offline Orders',
        }}
      />
      <Stack.Screen
        name="ProcessPayment"
        component={LazyProcessPayment}
        options={{ 
          title: 'Process Payment',
          presentation: 'modal',
        }}
      />
    </Stack.Navigator>
  );
};
