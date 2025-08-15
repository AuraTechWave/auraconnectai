import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { View, Text } from 'react-native';

// Placeholder screens - to be implemented
const StaffListScreen = () => (
  <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
    <Text>Staff List</Text>
  </View>
);

const StaffDetailsScreen = () => (
  <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
    <Text>Staff Details</Text>
  </View>
);

const ScheduleScreen = () => (
  <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
    <Text>Schedule</Text>
  </View>
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
