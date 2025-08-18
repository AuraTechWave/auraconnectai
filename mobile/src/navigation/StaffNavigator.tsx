import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { StaffListScreen } from '@screens/staff/StaffListScreen';
import { StaffDetailsScreen } from '@screens/staff/StaffDetailsScreen';
import { ScheduleScreen } from '@screens/staff/ScheduleScreen';

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
        component={StaffDetailsScreen}
        options={{ title: 'Staff Details' }}
      />
      <Stack.Screen
        name="Schedule"
        component={ScheduleScreen}
        options={{ title: 'Schedule' }}
      />
    </Stack.Navigator>
  );
};
