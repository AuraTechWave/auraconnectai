// Email validation
export const validateEmail = (email) => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!email) {
    return 'Email is required';
  }
  if (!emailRegex.test(email)) {
    return 'Please enter a valid email address';
  }
  return null;
};

// Phone validation
export const validatePhone = (phone) => {
  // Remove all non-digits
  const digitsOnly = phone.replace(/\D/g, '');
  
  if (!phone) {
    return 'Phone number is required';
  }
  
  // US phone number validation (10 digits)
  if (digitsOnly.length !== 10) {
    return 'Please enter a valid 10-digit phone number';
  }
  
  return null;
};

// Password validation
export const validatePassword = (password) => {
  if (!password) {
    return 'Password is required';
  }
  if (password.length < 8) {
    return 'Password must be at least 8 characters long';
  }
  if (!/[A-Z]/.test(password)) {
    return 'Password must contain at least one uppercase letter';
  }
  if (!/[a-z]/.test(password)) {
    return 'Password must contain at least one lowercase letter';
  }
  if (!/[0-9]/.test(password)) {
    return 'Password must contain at least one number';
  }
  return null;
};

// Name validation
export const validateName = (name, fieldName = 'Name') => {
  if (!name || !name.trim()) {
    return `${fieldName} is required`;
  }
  if (name.trim().length < 2) {
    return `${fieldName} must be at least 2 characters long`;
  }
  if (!/^[a-zA-Z\s'-]+$/.test(name)) {
    return `${fieldName} can only contain letters, spaces, hyphens, and apostrophes`;
  }
  return null;
};

// Address validation
export const validateAddress = (address) => {
  const errors = {};
  
  if (!address.street || !address.street.trim()) {
    errors.street = 'Street address is required';
  }
  
  if (!address.city || !address.city.trim()) {
    errors.city = 'City is required';
  } else if (!/^[a-zA-Z\s-]+$/.test(address.city)) {
    errors.city = 'City can only contain letters, spaces, and hyphens';
  }
  
  if (!address.state || !address.state.trim()) {
    errors.state = 'State is required';
  } else if (address.state.length !== 2) {
    errors.state = 'Please use 2-letter state code (e.g., CA, NY)';
  }
  
  if (!address.zipCode || !address.zipCode.trim()) {
    errors.zipCode = 'ZIP code is required';
  } else if (!/^\d{5}(-\d{4})?$/.test(address.zipCode)) {
    errors.zipCode = 'Please enter a valid ZIP code (e.g., 12345 or 12345-6789)';
  }
  
  return Object.keys(errors).length > 0 ? errors : null;
};

// Credit card validation
export const validateCreditCard = (card) => {
  const errors = {};
  
  // Card number validation (basic Luhn algorithm)
  if (!card.number) {
    errors.number = 'Card number is required';
  } else {
    const cleanNumber = card.number.replace(/\s/g, '');
    if (!/^\d{13,19}$/.test(cleanNumber)) {
      errors.number = 'Please enter a valid card number';
    } else if (!luhnCheck(cleanNumber)) {
      errors.number = 'Invalid card number';
    }
  }
  
  // Expiry validation
  if (!card.expiry) {
    errors.expiry = 'Expiry date is required';
  } else {
    const [month, year] = card.expiry.split('/').map(num => parseInt(num, 10));
    const currentDate = new Date();
    const currentYear = currentDate.getFullYear() % 100;
    const currentMonth = currentDate.getMonth() + 1;
    
    if (!month || month < 1 || month > 12) {
      errors.expiry = 'Invalid month';
    } else if (!year || year < currentYear || (year === currentYear && month < currentMonth)) {
      errors.expiry = 'Card has expired';
    }
  }
  
  // CVV validation
  if (!card.cvv) {
    errors.cvv = 'CVV is required';
  } else if (!/^\d{3,4}$/.test(card.cvv)) {
    errors.cvv = 'Invalid CVV';
  }
  
  // Name validation
  if (!card.name || !card.name.trim()) {
    errors.name = 'Cardholder name is required';
  }
  
  return Object.keys(errors).length > 0 ? errors : null;
};

// Luhn algorithm for credit card validation
function luhnCheck(cardNumber) {
  let sum = 0;
  let isEven = false;
  
  for (let i = cardNumber.length - 1; i >= 0; i--) {
    let digit = parseInt(cardNumber.charAt(i), 10);
    
    if (isEven) {
      digit *= 2;
      if (digit > 9) {
        digit -= 9;
      }
    }
    
    sum += digit;
    isEven = !isEven;
  }
  
  return sum % 10 === 0;
}

// Promo code validation
export const validatePromoCode = (code) => {
  if (!code || !code.trim()) {
    return 'Please enter a promo code';
  }
  if (code.length < 3) {
    return 'Promo code must be at least 3 characters';
  }
  if (!/^[A-Z0-9]+$/.test(code.toUpperCase())) {
    return 'Promo code can only contain letters and numbers';
  }
  return null;
};

// Order validation
export const validateOrder = (order) => {
  const errors = {};
  
  if (!order.items || order.items.length === 0) {
    errors.items = 'Your cart is empty';
  }
  
  if (!order.deliveryAddress) {
    errors.deliveryAddress = 'Delivery address is required';
  } else {
    const addressErrors = validateAddress(order.deliveryAddress);
    if (addressErrors) {
      errors.deliveryAddress = addressErrors;
    }
  }
  
  if (!order.paymentMethod) {
    errors.paymentMethod = 'Payment method is required';
  }
  
  if (order.paymentMethod === 'card' && order.paymentDetails) {
    const cardErrors = validateCreditCard(order.paymentDetails);
    if (cardErrors) {
      errors.paymentDetails = cardErrors;
    }
  }
  
  return Object.keys(errors).length > 0 ? errors : null;
};

// Form validation helper
export const validateForm = (formData, validationRules) => {
  const errors = {};
  
  Object.keys(validationRules).forEach(field => {
    const value = formData[field];
    const rules = validationRules[field];
    
    // Check required
    if (rules.required && (!value || (typeof value === 'string' && !value.trim()))) {
      errors[field] = rules.requiredMessage || `${field} is required`;
      return;
    }
    
    // Skip other validations if field is empty and not required
    if (!value) return;
    
    // Check pattern
    if (rules.pattern && !rules.pattern.test(value)) {
      errors[field] = rules.patternMessage || `Invalid ${field} format`;
    }
    
    // Check min length
    if (rules.minLength && value.length < rules.minLength) {
      errors[field] = `${field} must be at least ${rules.minLength} characters`;
    }
    
    // Check max length
    if (rules.maxLength && value.length > rules.maxLength) {
      errors[field] = `${field} must be no more than ${rules.maxLength} characters`;
    }
    
    // Custom validation
    if (rules.validate) {
      const error = rules.validate(value, formData);
      if (error) {
        errors[field] = error;
      }
    }
  });
  
  return Object.keys(errors).length > 0 ? errors : null;
};