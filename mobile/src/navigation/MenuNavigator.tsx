import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { View, Text } from 'react-native';

// Placeholder screens - to be implemented
const MenuListScreen = () => (
  <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
    <Text>Menu List</Text>
  </View>
);

const MenuItemDetailsScreen = () => (
  <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
    <Text>Menu Item Details</Text>
  </View>
);

const CategoriesScreen = () => (
  <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
    <Text>Categories</Text>
  </View>
);

export type MenuStackParamList = {
  MenuList: undefined;
  MenuItemDetails: { itemId: number };
  Categories: undefined;
};

const Stack = createNativeStackNavigator<MenuStackParamList>();

export const MenuNavigator: React.FC = () => {
  return (
    <Stack.Navigator>
      <Stack.Screen
        name="MenuList"
        component={MenuListScreen}
        options={{ title: 'Menu' }}
      />
      <Stack.Screen
        name="MenuItemDetails"
        component={MenuItemDetailsScreen}
        options={{ title: 'Item Details' }}
      />
      <Stack.Screen
        name="Categories"
        component={CategoriesScreen}
        options={{ title: 'Categories' }}
      />
    </Stack.Navigator>
  );
};