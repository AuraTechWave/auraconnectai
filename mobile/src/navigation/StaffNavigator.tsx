import React, { lazy, Suspense } from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { View, ActivityIndicator } from 'react-native';
import { StaffListScreen } from '@screens/staff/StaffListScreen';
import { designSystem } from '@constants/designSystem';

// Lazy load heavy screens
const StaffDetailsScreen = lazy(() => import('@screens/staff/StaffDetailsScreen').then(module => ({ default: module.StaffDetailsScreen })));
const ScheduleScreen = lazy(() => import('@screens/staff/ScheduleScreen').then(module => ({ default: module.ScheduleScreen })));

// Loading component
const ScreenLoader = () => (
  <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
    <ActivityIndicator size="large" color={designSystem.colors.semantic.primary} />
  </View>
);

// Wrap lazy components
const LazyStaffDetails = (props: any) => (
  <Suspense fallback={<ScreenLoader />}>
    <StaffDetailsScreen {...props} />
  </Suspense>
);

const LazySchedule = (props: any) => (
  <Suspense fallback={<ScreenLoader />}>
    <ScheduleScreen {...props} />
  </Suspense>
);

export type StaffStackParamList = {
  StaffList: undefined;
  StaffDetails: { staffId: number };
  Schedule: undefined;
};

const Stack = createNativeStackNavigator<StaffStackParamList>();

export const StaffNavigator: React.FC = () => {
  return (
    <Stack.Navigator>
      <Stack.Screen
        name="StaffList"
        component={StaffListScreen}
        options={{ title: 'Staff' }}
      />
      <Stack.Screen
        name="StaffDetails"
        component={LazyStaffDetails}
        options={{ title: 'Staff Details' }}
      />
      <Stack.Screen
        name="Schedule"
        component={LazySchedule}
        options={{ title: 'Schedule' }}
      />
    </Stack.Navigator>
  );
};
