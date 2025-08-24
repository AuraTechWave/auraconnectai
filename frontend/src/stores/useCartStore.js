import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

const useCartStore = create(
  persist(
    (set, get) => ({
      items: [],
      restaurantId: null,
      orderType: 'dine-in',
      tableNumber: null,
      specialInstructions: '',
      appliedPromoCode: null,
      discount: 0,
      
      addItem: (item) => {
        set((state) => {
          const existingItem = state.items.find(
            (cartItem) => 
              cartItem.id === item.id && 
              JSON.stringify(cartItem.modifiers) === JSON.stringify(item.modifiers)
          );

          if (existingItem) {
            return {
              items: state.items.map((cartItem) =>
                cartItem === existingItem
                  ? { ...cartItem, quantity: cartItem.quantity + 1 }
                  : cartItem
              ),
            };
          }

          return {
            items: [...state.items, { ...item, quantity: 1, cartId: Date.now() }],
          };
        });
      },

      updateItemQuantity: (cartId, quantity) => {
        if (quantity <= 0) {
          get().removeItem(cartId);
          return;
        }

        set((state) => ({
          items: state.items.map((item) =>
            item.cartId === cartId ? { ...item, quantity } : item
          ),
        }));
      },

      removeItem: (cartId) => {
        set((state) => ({
          items: state.items.filter((item) => item.cartId !== cartId),
        }));
      },

      clearCart: () => {
        set({
          items: [],
          restaurantId: null,
          orderType: 'dine-in',
          tableNumber: null,
          specialInstructions: '',
          appliedPromoCode: null,
          discount: 0,
        });
      },

      setOrderType: (type) => set({ orderType: type }),
      
      setTableNumber: (number) => set({ tableNumber: number }),
      
      setSpecialInstructions: (instructions) => set({ specialInstructions: instructions }),
      
      setRestaurantId: (id) => set({ restaurantId: id }),

      applyPromoCode: (code, discount) => {
        set({ appliedPromoCode: code, discount });
      },

      removePromoCode: () => {
        set({ appliedPromoCode: null, discount: 0 });
      },

      getSubtotal: () => {
        const items = get().items;
        return items.reduce((total, item) => {
          const itemPrice = item.price || 0;
          const modifiersPrice = (item.modifiers || []).reduce(
            (sum, mod) => sum + (mod.price || 0),
            0
          );
          return total + (itemPrice + modifiersPrice) * item.quantity;
        }, 0);
      },

      getTax: () => {
        const subtotal = get().getSubtotal();
        const taxRate = 0.0875;
        return subtotal * taxRate;
      },

      getTotal: () => {
        const subtotal = get().getSubtotal();
        const tax = get().getTax();
        const discount = get().discount || 0;
        return subtotal + tax - discount;
      },

      getItemCount: () => {
        return get().items.reduce((count, item) => count + item.quantity, 0);
      },

      canAddItem: (restaurantId) => {
        const currentRestaurantId = get().restaurantId;
        return !currentRestaurantId || currentRestaurantId === restaurantId;
      },

      getCartSummary: () => {
        const state = get();
        return {
          items: state.items,
          subtotal: state.getSubtotal(),
          tax: state.getTax(),
          discount: state.discount,
          total: state.getTotal(),
          itemCount: state.getItemCount(),
          orderType: state.orderType,
          tableNumber: state.tableNumber,
          specialInstructions: state.specialInstructions,
          appliedPromoCode: state.appliedPromoCode,
        };
      },
    }),
    {
      name: 'cart-storage',
      storage: createJSONStorage(() => localStorage),
    }
  )
);

export default useCartStore;