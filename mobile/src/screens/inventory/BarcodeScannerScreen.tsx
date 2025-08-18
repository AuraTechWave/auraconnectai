import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  StyleSheet,
  Alert,
  Vibration,
  Platform,
  TouchableOpacity,
} from 'react-native';
import {
  Text,
  IconButton,
  useTheme,
  Portal,
  Modal,
  Button,
  TextInput,
  Card,
  Chip,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { InventoryStackParamList } from '@navigation/InventoryNavigator';
import { useMutation, useQuery } from '@tanstack/react-query';
// import { Camera, CameraView } from 'expo-camera'; // TODO: Install expo-camera

type RouteProps = RouteProp<InventoryStackParamList, 'BarcodeScanner'>;

interface ScannedItem {
  id?: number;
  barcode: string;
  name: string;
  sku: string;
  category: string;
  currentStock: number;
  unit: string;
}

export const BarcodeScannerScreen: React.FC = () => {
  const theme = useTheme();
  const route = useRoute<RouteProps>();
  const navigation = useNavigation();
  const { mode } = route.params;
  
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [scanned, setScanned] = useState(false);
  const [scannedData, setScannedData] = useState<string>('');
  const [torchOn, setTorchOn] = useState(false);
  const [showManualEntry, setShowManualEntry] = useState(false);
  const [manualBarcode, setManualBarcode] = useState('');
  const [showResultModal, setShowResultModal] = useState(false);
  const [scannedItem, setScannedItem] = useState<ScannedItem | null>(null);
  const [quantity, setQuantity] = useState('1');

  useEffect(() => {
    // TODO: Uncomment when expo-camera is installed
    // (async () => {
    //   const { status } = await Camera.requestCameraPermissionsAsync();
    //   setHasPermission(status === 'granted');
    // })();
    setHasPermission(true); // Temporary for development
  }, []);

  // Query to lookup item by barcode
  const lookupItemMutation = useMutation({
    mutationFn: async (barcode: string) => {
      // TODO: Replace with actual API call
      // Simulate API lookup
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Mock data
      const mockItems: Record<string, ScannedItem> = {
        '1234567890123': {
          id: 1,
          barcode: '1234567890123',
          name: 'Premium Coffee Beans',
          sku: 'COF-001',
          category: 'Beverages',
          currentStock: 45,
          unit: 'kg',
        },
        '2345678901234': {
          id: 2,
          barcode: '2345678901234',
          name: 'Organic Milk',
          sku: 'DAI-001',
          category: 'Dairy',
          currentStock: 8,
          unit: 'liters',
        },
      };

      const item = mockItems[barcode];
      if (!item && mode === 'add') {
        // New item
        return {
          barcode,
          name: '',
          sku: '',
          category: '',
          currentStock: 0,
          unit: '',
        };
      }
      
      if (!item) {
        throw new Error('Item not found');
      }
      
      return item;
    },
    onSuccess: (item) => {
      setScannedItem(item);
      setShowResultModal(true);
    },
    onError: () => {
      Alert.alert(
        'Item Not Found',
        'No item found with this barcode. Would you like to add it?',
        [
          { text: 'Cancel', onPress: resetScanner },
          { text: 'Add Item', onPress: () => handleAddNewItem(scannedData) },
        ],
      );
    },
  });

  const handleBarCodeScanned = ({ type, data }: { type: string; data: string }) => {
    if (scanned) return;
    
    setScanned(true);
    setScannedData(data);
    Vibration.vibrate(100);
    
    lookupItemMutation.mutate(data);
  };

  const handleManualEntry = () => {
    if (!manualBarcode) {
      Alert.alert('Error', 'Please enter a barcode');
      return;
    }
    
    setScannedData(manualBarcode);
    setShowManualEntry(false);
    lookupItemMutation.mutate(manualBarcode);
  };

  const resetScanner = () => {
    setScanned(false);
    setScannedData('');
    setManualBarcode('');
    setShowResultModal(false);
    setScannedItem(null);
    setQuantity('1');
  };

  const handleAddNewItem = (barcode: string) => {
    // Navigate to add item screen with barcode pre-filled
    navigation.navigate('AddInventoryItem' as any, { barcode });
  };

  const handleItemAction = () => {
    if (!scannedItem) return;

    switch (mode) {
      case 'search':
        navigation.navigate('InventoryItem', { itemId: scannedItem.id! });
        break;
      case 'add':
        if (scannedItem.id) {
          // Existing item - update quantity
          Alert.alert('Update Stock', `Added ${quantity} ${scannedItem.unit} to ${scannedItem.name}`);
        } else {
          // New item
          handleAddNewItem(scannedItem.barcode);
        }
        break;
      case 'count':
        // Handle inventory count
        Alert.alert('Count Recorded', `Counted ${quantity} ${scannedItem.unit} of ${scannedItem.name}`);
        break;
    }
    
    resetScanner();
  };

  const renderScannerOverlay = () => (
    <>
      <View style={styles.scannerOverlay}>
        <View style={styles.scannerHeader}>
          <IconButton
            icon="arrow-left"
            size={24}
            iconColor="white"
            onPress={() => navigation.goBack()}
          />
          <Text variant="titleLarge" style={styles.scannerTitle}>
            {mode === 'add' ? 'Add Item' : mode === 'search' ? 'Search Item' : 'Count Item'}
          </Text>
          <IconButton
            icon={torchOn ? 'flashlight' : 'flashlight-off'}
            size={24}
            iconColor="white"
            onPress={() => setTorchOn(!torchOn)}
          />
        </View>

        <View style={styles.scannerFrame}>
          <View style={[styles.corner, styles.topLeft]} />
          <View style={[styles.corner, styles.topRight]} />
          <View style={[styles.corner, styles.bottomLeft]} />
          <View style={[styles.corner, styles.bottomRight]} />
        </View>

        <Text variant="bodyLarge" style={styles.scannerHint}>
          Position barcode within the frame
        </Text>

        <TouchableOpacity
          style={styles.manualButton}
          onPress={() => setShowManualEntry(true)}>
          <IconButton icon="keyboard" size={20} iconColor="white" />
          <Text variant="bodyMedium" style={styles.manualButtonText}>
            Enter manually
          </Text>
        </TouchableOpacity>
      </View>
    </>
  );

  const renderResultModal = () => (
    <Portal>
      <Modal
        visible={showResultModal}
        onDismiss={resetScanner}
        contentContainerStyle={styles.modalContent}>
        {scannedItem && (
          <>
            <Text variant="headlineSmall" style={styles.modalTitle}>
              {scannedItem.id ? 'Item Found' : 'New Item'}
            </Text>
            
            <Card style={styles.itemCard}>
              <Card.Content>
                <Text variant="titleMedium">{scannedItem.name || 'Unknown Item'}</Text>
                <Text variant="bodySmall" style={styles.itemDetails}>
                  SKU: {scannedItem.sku || 'N/A'} • Barcode: {scannedItem.barcode}
                </Text>
                {scannedItem.id && (
                  <>
                    <Chip style={styles.categoryChip}>{scannedItem.category}</Chip>
                    <Text variant="bodyMedium" style={styles.stockInfo}>
                      Current Stock: {scannedItem.currentStock} {scannedItem.unit}
                    </Text>
                  </>
                )}
              </Card.Content>
            </Card>

            {(mode === 'add' || mode === 'count') && scannedItem.id && (
              <TextInput
                label="Quantity"
                value={quantity}
                onChangeText={setQuantity}
                keyboardType="numeric"
                mode="outlined"
                style={styles.quantityInput}
                right={<TextInput.Affix text={scannedItem.unit} />}
              />
            )}

            <View style={styles.modalActions}>
              <Button mode="outlined" onPress={resetScanner}>
                Cancel
              </Button>
              <Button mode="contained" onPress={handleItemAction}>
                {mode === 'search' ? 'View Details' : 
                 mode === 'add' ? (scannedItem.id ? 'Add Stock' : 'Create Item') :
                 'Record Count'}
              </Button>
            </View>
          </>
        )}
      </Modal>
    </Portal>
  );

  const renderManualEntryModal = () => (
    <Portal>
      <Modal
        visible={showManualEntry}
        onDismiss={() => setShowManualEntry(false)}
        contentContainerStyle={styles.modalContent}>
        <Text variant="headlineSmall" style={styles.modalTitle}>
          Enter Barcode
        </Text>
        
        <TextInput
          label="Barcode"
          value={manualBarcode}
          onChangeText={setManualBarcode}
          keyboardType="numeric"
          mode="outlined"
          style={styles.barcodeInput}
          autoFocus
        />

        <View style={styles.modalActions}>
          <Button mode="outlined" onPress={() => setShowManualEntry(false)}>
            Cancel
          </Button>
          <Button mode="contained" onPress={handleManualEntry}>
            Search
          </Button>
        </View>
      </Modal>
    </Portal>
  );

  if (hasPermission === null) {
    return (
      <SafeAreaView style={styles.container}>
        <Text>Requesting camera permission...</Text>
      </SafeAreaView>
    );
  }

  if (hasPermission === false) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.noPermission}>
          <Text variant="headlineSmall">Camera Permission Required</Text>
          <Text variant="bodyLarge" style={styles.permissionText}>
            Please grant camera permission to scan barcodes
          </Text>
          <Button mode="contained" onPress={() => {
            // TODO: Camera.requestCameraPermissionsAsync()
            Alert.alert('Info', 'Camera permission would be requested here');
          }}>
            Grant Permission
          </Button>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <View style={styles.container}>
      {/* TODO: Add CameraView when expo-camera is installed */}
      <View style={[StyleSheet.absoluteFillObject, { backgroundColor: '#000' }]}>
        <View style={styles.cameraPlaceholder}>
          <Text variant="bodyLarge" style={{ color: 'white', textAlign: 'center' }}>
            Camera preview would appear here.{'\n'}
            Use "Enter manually" button below.
          </Text>
        </View>
      </View>
      
      {renderScannerOverlay()}
      {renderResultModal()}
      {renderManualEntryModal()}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  cameraPlaceholder: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scannerOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
  },
  scannerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 50,
    paddingHorizontal: 8,
  },
  scannerTitle: {
    color: 'white',
    fontWeight: '600',
  },
  scannerFrame: {
    width: 280,
    height: 280,
    alignSelf: 'center',
    marginTop: 100,
    position: 'relative',
  },
  corner: {
    position: 'absolute',
    width: 40,
    height: 40,
    borderColor: 'white',
    borderWidth: 3,
  },
  topLeft: {
    top: 0,
    left: 0,
    borderRightWidth: 0,
    borderBottomWidth: 0,
  },
  topRight: {
    top: 0,
    right: 0,
    borderLeftWidth: 0,
    borderBottomWidth: 0,
  },
  bottomLeft: {
    bottom: 0,
    left: 0,
    borderRightWidth: 0,
    borderTopWidth: 0,
  },
  bottomRight: {
    bottom: 0,
    right: 0,
    borderLeftWidth: 0,
    borderTopWidth: 0,
  },
  scannerHint: {
    color: 'white',
    textAlign: 'center',
    marginTop: 32,
  },
  manualButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'absolute',
    bottom: 100,
    alignSelf: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 24,
  },
  manualButtonText: {
    color: 'white',
    marginLeft: -8,
  },
  noPermission: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  permissionText: {
    textAlign: 'center',
    marginVertical: 16,
    color: '#64748b',
  },
  modalContent: {
    backgroundColor: 'white',
    padding: 24,
    margin: 20,
    borderRadius: 8,
  },
  modalTitle: {
    marginBottom: 24,
  },
  itemCard: {
    marginBottom: 16,
  },
  itemDetails: {
    color: '#64748b',
    marginTop: 4,
  },
  categoryChip: {
    alignSelf: 'flex-start',
    marginTop: 8,
  },
  stockInfo: {
    marginTop: 12,
  },
  quantityInput: {
    marginBottom: 24,
  },
  barcodeInput: {
    marginBottom: 24,
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
  },
});