import React, { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import { Divider, RadioButton, Checkbox } from 'react-native-paper';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import {
  Card,
  CardContent,
  Button,
  Input,
  colors,
  spacing,
  typography,
  borderRadius,
  shadows,
} from '../../components/ui';

interface PaymentMethod {
  id: string;
  type: 'cash' | 'card' | 'digital' | 'check';
  name: string;
  icon: string;
  fee?: number;
}

const ProcessPaymentScreen: React.FC = () => {
  const route = useRoute<any>();
  const navigation = useNavigation<any>();
  
  // Type guard for orderId - support both string and number for backward compatibility
  const orderId = route.params?.orderId;
  const orderIdString = typeof orderId === 'number' ? orderId.toString() : orderId;
  
  // Guard against undefined orderId
  if (!orderId) {
    // Handle missing orderId - navigate back or show error
    React.useEffect(() => {
      Alert.alert('Error', 'Order ID is missing', [
        { text: 'OK', onPress: () => navigation.goBack() }
      ]);
    }, []);
    return null;
  }

  const [selectedMethod, setSelectedMethod] = useState<string>('card');
  const [tipAmount, setTipAmount] = useState<string>('');
  const [tipPercentage, setTipPercentage] = useState<number>(15);
  const [isProcessing, setIsProcessing] = useState(false);
  const [saveCard, setSaveCard] = useState(false);
  const [emailReceipt, setEmailReceipt] = useState(true);
  const [splitPayment, setSplitPayment] = useState(false);

  // Mock order data - replace with actual data fetching using orderIdString
  // TODO: Use orderIdString for API call: fetchOrder(orderIdString)
  const orderData = {
    orderNumber: '#ORD-001',
    subtotal: 30.96,
    tax: 3.71,
    total: 34.67,
  };

  const paymentMethods: PaymentMethod[] = [
    { id: 'cash', type: 'cash', name: 'Cash', icon: 'cash' },
    { id: 'card', type: 'card', name: 'Credit/Debit Card', icon: 'credit-card' },
    { id: 'digital', type: 'digital', name: 'Digital Wallet', icon: 'cellphone-nfc' },
    { id: 'check', type: 'check', name: 'Check', icon: 'checkbook' },
  ];

  const tipPercentages = [10, 15, 18, 20, 25];

  const calculateTip = (percentage: number) => {
    const tip = (orderData.subtotal * percentage) / 100;
    setTipAmount(tip.toFixed(2));
    setTipPercentage(percentage);
  };

  const getTotalWithTip = () => {
    const tip = parseFloat(tipAmount) || 0;
    return (orderData.total + tip).toFixed(2);
  };

  const handleProcessPayment = async () => {
    setIsProcessing(true);
    
    // Simulate payment processing
    setTimeout(() => {
      setIsProcessing(false);
      Alert.alert(
        'Payment Successful',
        `Payment of $${getTotalWithTip()} has been processed successfully.`,
        [
          {
            text: 'OK',
            onPress: () => {
              navigation.navigate('OrderDetails', { orderId: orderIdString, paymentProcessed: true });
            },
          },
        ]
      );
    }, 2000);
  };

  const renderPaymentMethod = (method: PaymentMethod) => (
    <TouchableOpacity
      key={method.id}
      style={[
        styles.paymentMethodCard,
        selectedMethod === method.id && styles.selectedPaymentMethod,
      ]}
      onPress={() => setSelectedMethod(method.id)}
      activeOpacity={0.7}
    >
      <View style={styles.paymentMethodContent}>
        <MaterialCommunityIcons
          name={method.icon}
          size={24}
          color={selectedMethod === method.id ? colors.primary[500] : colors.text.secondary}
        />
        <Text
          style={[
            styles.paymentMethodName,
            selectedMethod === method.id && styles.selectedPaymentMethodName,
          ]}
        >
          {method.name}
        </Text>
      </View>
      <RadioButton
        value={method.id}
        status={selectedMethod === method.id ? 'checked' : 'unchecked'}
        onPress={() => setSelectedMethod(method.id)}
        color={colors.primary[500]}
      />
    </TouchableOpacity>
  );

  const renderCardForm = () => {
    if (selectedMethod !== 'card') return null;

    return (
      <Card variant="outlined" style={styles.cardFormContainer}>
        <CardContent>
          <Input
            label="Card Number"
            placeholder="1234 5678 9012 3456"
            leftIcon="credit-card"
            keyboardType="numeric"
            maxLength={19}
            style={styles.input}
          />
          <View style={styles.cardRow}>
            <Input
              label="Expiry Date"
              placeholder="MM/YY"
              keyboardType="numeric"
              maxLength={5}
              containerStyle={styles.halfInput}
            />
            <Input
              label="CVV"
              placeholder="123"
              keyboardType="numeric"
              maxLength={4}
              secureTextEntry
              containerStyle={styles.halfInput}
            />
          </View>
          <Input
            label="Cardholder Name"
            placeholder="John Doe"
            leftIcon="account"
            style={styles.input}
          />
          <View style={styles.checkboxRow}>
            <Checkbox
              status={saveCard ? 'checked' : 'unchecked'}
              onPress={() => setSaveCard(!saveCard)}
              color={colors.primary[500]}
            />
            <Text style={styles.checkboxLabel}>Save card for future payments</Text>
          </View>
        </CardContent>
      </Card>
    );
  };

  return (
    <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
      {/* Order Summary */}
      <Card variant="elevated" style={styles.section}>
        <CardContent>
          <Text style={styles.sectionTitle}>Order Summary</Text>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Order Number</Text>
            <Text style={styles.summaryValue}>{orderData.orderNumber}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Subtotal</Text>
            <Text style={styles.summaryValue}>${orderData.subtotal.toFixed(2)}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Tax</Text>
            <Text style={styles.summaryValue}>${orderData.tax.toFixed(2)}</Text>
          </View>
          <Divider style={styles.divider} />
          <View style={styles.summaryRow}>
            <Text style={styles.totalLabel}>Total</Text>
            <Text style={styles.totalValue}>${orderData.total.toFixed(2)}</Text>
          </View>
        </CardContent>
      </Card>

      {/* Tip Section */}
      <Card variant="elevated" style={styles.section}>
        <CardContent>
          <Text style={styles.sectionTitle}>Add Tip</Text>
          <View style={styles.tipPercentages}>
            {tipPercentages.map((percentage) => (
              <TouchableOpacity
                key={percentage}
                style={[
                  styles.tipButton,
                  tipPercentage === percentage && styles.selectedTipButton,
                ]}
                onPress={() => calculateTip(percentage)}
              >
                <Text
                  style={[
                    styles.tipButtonText,
                    tipPercentage === percentage && styles.selectedTipButtonText,
                  ]}
                >
                  {percentage}%
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <Input
            label="Custom Tip Amount"
            placeholder="0.00"
            value={tipAmount}
            onChangeText={setTipAmount}
            keyboardType="decimal-pad"
            leftIcon="cash"
            style={styles.input}
          />
        </CardContent>
      </Card>

      {/* Payment Method */}
      <Card variant="elevated" style={styles.section}>
        <CardContent>
          <Text style={styles.sectionTitle}>Payment Method</Text>
          {paymentMethods.map(renderPaymentMethod)}
        </CardContent>
      </Card>

      {/* Card Form */}
      {renderCardForm()}

      {/* Additional Options */}
      <Card variant="elevated" style={styles.section}>
        <CardContent>
          <Text style={styles.sectionTitle}>Additional Options</Text>
          <View style={styles.checkboxRow}>
            <Checkbox
              status={emailReceipt ? 'checked' : 'unchecked'}
              onPress={() => setEmailReceipt(!emailReceipt)}
              color={colors.primary[500]}
            />
            <Text style={styles.checkboxLabel}>Email receipt to customer</Text>
          </View>
          <View style={styles.checkboxRow}>
            <Checkbox
              status={splitPayment ? 'checked' : 'unchecked'}
              onPress={() => setSplitPayment(!splitPayment)}
              color={colors.primary[500]}
            />
            <Text style={styles.checkboxLabel}>Split payment</Text>
          </View>
        </CardContent>
      </Card>

      {/* Total with Tip */}
      <Card variant="elevated" style={[styles.section, styles.finalTotal]}>
        <CardContent>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Order Total</Text>
            <Text style={styles.summaryValue}>${orderData.total.toFixed(2)}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Tip</Text>
            <Text style={styles.summaryValue}>
              ${parseFloat(tipAmount || '0').toFixed(2)}
            </Text>
          </View>
          <Divider style={styles.divider} />
          <View style={styles.summaryRow}>
            <Text style={styles.finalTotalLabel}>Total Amount</Text>
            <Text style={styles.finalTotalValue}>${getTotalWithTip()}</Text>
          </View>
        </CardContent>
      </Card>

      {/* Process Payment Button */}
      <View style={styles.buttonContainer}>
        <Button
          title={isProcessing ? 'Processing...' : `Process Payment $${getTotalWithTip()}`}
          variant="primary"
          size="large"
          onPress={handleProcessPayment}
          disabled={isProcessing}
          loading={isProcessing}
          fullWidth
          icon={!isProcessing ? 'check-circle' : undefined}
        />
        <Button
          title="Cancel"
          variant="outline"
          size="large"
          onPress={() => navigation.goBack()}
          disabled={isProcessing}
          fullWidth
          style={styles.cancelButton}
        />
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background.secondary,
  },
  section: {
    marginHorizontal: spacing.md,
    marginTop: spacing.md,
  },
  sectionTitle: {
    fontSize: typography.fontSize.subtitle,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.text.primary,
    marginBottom: spacing.md,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  summaryLabel: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
  },
  summaryValue: {
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
  },
  totalLabel: {
    fontSize: typography.fontSize.bodyLarge,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.primary,
  },
  totalValue: {
    fontSize: typography.fontSize.subtitle,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.text.primary,
  },
  divider: {
    marginVertical: spacing.sm,
  },
  tipPercentages: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  tipButton: {
    flex: 1,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.xxs,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border.default,
    alignItems: 'center',
  },
  selectedTipButton: {
    backgroundColor: colors.primary[500],
    borderColor: colors.primary[500],
  },
  tipButtonText: {
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
  },
  selectedTipButtonText: {
    color: colors.text.inverse,
    fontWeight: typography.fontWeight.medium,
  },
  paymentMethodCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border.default,
    backgroundColor: colors.background.primary,
  },
  selectedPaymentMethod: {
    borderColor: colors.primary[500],
    backgroundColor: colors.primary[50],
  },
  paymentMethodContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  paymentMethodName: {
    fontSize: typography.fontSize.bodyLarge,
    color: colors.text.primary,
    marginLeft: spacing.sm,
  },
  selectedPaymentMethodName: {
    color: colors.primary[600],
    fontWeight: typography.fontWeight.medium,
  },
  cardFormContainer: {
    marginHorizontal: spacing.md,
    marginTop: spacing.md,
  },
  input: {
    marginBottom: spacing.sm,
  },
  cardRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  halfInput: {
    flex: 1,
    marginHorizontal: spacing.xs,
  },
  checkboxRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  checkboxLabel: {
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    marginLeft: spacing.xs,
  },
  finalTotal: {
    backgroundColor: colors.primary[50],
    borderColor: colors.primary[200],
    borderWidth: 1,
  },
  finalTotalLabel: {
    fontSize: typography.fontSize.subtitle,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.primary[700],
  },
  finalTotalValue: {
    fontSize: typography.fontSize.h3,
    fontWeight: typography.fontWeight.bold,
    color: colors.primary[600],
  },
  buttonContainer: {
    padding: spacing.md,
    paddingBottom: spacing.xl,
  },
  cancelButton: {
    marginTop: spacing.sm,
  },
});

export default ProcessPaymentScreen;