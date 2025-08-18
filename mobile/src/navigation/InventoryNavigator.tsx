import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { InventoryListScreen } from '@screens/inventory/InventoryListScreen';
import { InventoryItemScreen } from '@screens/inventory/InventoryItemScreen';
import { BarcodeScannerScreen } from '@screens/inventory/BarcodeScannerScreen';
import { InventoryCountScreen } from '@screens/inventory/InventoryCountScreen';

export type InventoryStackParamList = {
  InventoryList: undefined;
  InventoryItem: { itemId: number };
  BarcodeScanner: { mode: 'add' | 'search' | 'count' };
  InventoryCount: { sessionId?: string };
};

const Stack = createNativeStackNavigator<InventoryStackParamList>();

export const InventoryNavigator: React.FC = () => {
  return (
    <Stack.Navigator>
      <Stack.Screen
        name="InventoryList"
        component={InventoryListScreen}
        options={{ title: 'Inventory' }}
      />
      <Stack.Screen
        name="InventoryItem"
        component={InventoryItemScreen}
        options={{ title: 'Item Details' }}
      />
      <Stack.Screen
        name="BarcodeScanner"
        component={BarcodeScannerScreen}
        options={{ title: 'Scan Barcode' }}
      />
      <Stack.Screen
        name="InventoryCount"
        component={InventoryCountScreen}
        options={{ title: 'Inventory Count' }}
      />
    </Stack.Navigator>
  );
};