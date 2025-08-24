import api, { apiWithRetry } from './api';
import { 
  generateUUID, 
  idempotentRequest, 
  createCheckoutIdempotencyKey,
  rateLimit 
} from '../utils/idempotency';
import { validateOrder, validatePromoCode } from '../utils/validation';

class CheckoutService {
  // Validate promo code with rate limiting
  async validatePromoCode(code) {
    // Rate limit promo code attempts
    const rateLimitCheck = rateLimit(`promo_${code}`, 5, 60000); // 5 attempts per minute
    if (!rateLimitCheck.allowed) {
      throw new Error(rateLimitCheck.message);
    }

    // Validate format
    const validationError = validatePromoCode(code);
    if (validationError) {
      throw new Error(validationError);
    }

    try {
      const response = await api.post('/api/checkout/validate-promo', {
        code: code.toUpperCase()
      });
      return response.data;
    } catch (error) {
      if (error.status === 404) {
        throw new Error('Invalid promo code');
      }
      throw error;
    }
  }

  // Calculate order totals with server validation
  async calculateTotals(orderData) {
    try {
      const response = await api.post('/api/checkout/calculate', {
        items: orderData.items,
        promo_code: orderData.promoCode,
        delivery_address: orderData.deliveryAddress,
        tip_amount: orderData.tipAmount
      });
      return response.data;
    } catch (error) {
      throw new Error(error.message || 'Failed to calculate order totals');
    }
  }

  // Validate cart items availability
  async validateCart(items) {
    try {
      const response = await api.post('/api/checkout/validate-cart', { items });
      return response.data;
    } catch (error) {
      throw new Error(error.message || 'Failed to validate cart');
    }
  }

  // Create order with idempotency
  async createOrder(orderData) {
    // Validate order data
    const validationErrors = validateOrder(orderData);
    if (validationErrors) {
      throw new Error('Invalid order data', { cause: validationErrors });
    }

    // Generate idempotency key
    const customerId = orderData.customerId || 'guest';
    const timestamp = Date.now();
    const idempotencyKey = createCheckoutIdempotencyKey(
      orderData.items,
      customerId,
      timestamp
    );

    // Create order with idempotency
    return idempotentRequest(
      idempotencyKey,
      async () => {
        // First validate cart and calculate totals
        const [cartValidation, totals] = await Promise.all([
          this.validateCart(orderData.items),
          this.calculateTotals(orderData)
        ]);

        if (!cartValidation.valid) {
          throw new Error(cartValidation.message || 'Cart validation failed');
        }

        // Create the order
        const response = await apiWithRetry.post('/api/orders', {
          ...orderData,
          idempotency_key: idempotencyKey,
          calculated_totals: totals,
          order_uuid: generateUUID(),
          created_at: new Date().toISOString()
        });

        return response.data;
      },
      { ttl: 600000 } // 10 minutes TTL for checkout
    );
  }

  // Process payment with idempotency
  async processPayment(orderId, paymentData) {
    const idempotencyKey = `payment_${orderId}_${Date.now()}`;

    return idempotentRequest(
      idempotencyKey,
      async () => {
        const response = await apiWithRetry.post(`/api/orders/${orderId}/payment`, {
          ...paymentData,
          idempotency_key: idempotencyKey
        });

        return response.data;
      },
      { ttl: 300000 } // 5 minutes TTL
    );
  }

  // Complete checkout flow
  async checkout(checkoutData) {
    try {
      // Step 1: Create order
      const order = await this.createOrder({
        items: checkoutData.items,
        customerId: checkoutData.customerId,
        deliveryAddress: checkoutData.deliveryAddress,
        deliveryInstructions: checkoutData.deliveryInstructions,
        promoCode: checkoutData.promoCode,
        tipAmount: checkoutData.tipAmount,
        paymentMethod: checkoutData.paymentMethod
      });

      // Step 2: Process payment
      if (checkoutData.paymentMethod === 'card') {
        const payment = await this.processPayment(order.id, {
          method: 'card',
          card_token: checkoutData.cardToken,
          amount: order.total_amount,
          save_card: checkoutData.saveCard
        });

        // Update order with payment status
        order.payment_status = payment.status;
        order.payment_id = payment.id;
      }

      return {
        success: true,
        order,
        message: 'Order placed successfully'
      };
    } catch (error) {
      console.error('Checkout failed:', error);
      
      // Check if it's a validation error with details
      if (error.cause) {
        return {
          success: false,
          errors: error.cause,
          message: 'Please fix the validation errors'
        };
      }

      return {
        success: false,
        message: error.message || 'Checkout failed. Please try again.'
      };
    }
  }

  // Get estimated delivery time
  async getDeliveryEstimate(address) {
    try {
      const response = await api.post('/api/checkout/delivery-estimate', { address });
      return response.data;
    } catch (error) {
      // Return default estimate if API fails
      return {
        estimated_minutes: 45,
        estimated_time: new Date(Date.now() + 45 * 60000).toISOString()
      };
    }
  }

  // Apply tips
  calculateTip(subtotal, percentage) {
    const tipAmount = (subtotal * percentage) / 100;
    return Math.round(tipAmount * 100) / 100; // Round to 2 decimals
  }

  // Format price
  formatPrice(amount) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  }
}

export default new CheckoutService();