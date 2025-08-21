/**
 * Privacy utilities for handling sensitive data
 * Ensures PII and payment information is properly redacted
 */

interface RedactionOptions {
  showLastDigits?: number;
  replaceWith?: string;
  preserveLength?: boolean;
}

// Redact credit card numbers
export const redactCardNumber = (
  cardNumber: string,
  options: RedactionOptions = {}
): string => {
  const { showLastDigits = 4, replaceWith = '*' } = options;
  const cleaned = cardNumber.replace(/\s/g, '');
  
  if (cleaned.length <= showLastDigits) {
    return cleaned;
  }
  
  const visiblePart = cleaned.slice(-showLastDigits);
  const hiddenLength = cleaned.length - showLastDigits;
  const hiddenPart = replaceWith.repeat(hiddenLength);
  
  // Format as card number (e.g., **** **** **** 1234)
  return `${hiddenPart}${visiblePart}`.replace(/(.{4})/g, '$1 ').trim();
};

// Redact phone numbers
export const redactPhoneNumber = (
  phone: string,
  options: RedactionOptions = {}
): string => {
  const { showLastDigits = 4, replaceWith = '*' } = options;
  const cleaned = phone.replace(/\D/g, '');
  
  if (cleaned.length <= showLastDigits) {
    return phone;
  }
  
  const visiblePart = cleaned.slice(-showLastDigits);
  const hiddenLength = cleaned.length - showLastDigits;
  const hiddenPart = replaceWith.repeat(hiddenLength);
  
  return `${hiddenPart}${visiblePart}`;
};

// Redact email addresses
export const redactEmail = (email: string): string => {
  const [localPart, domain] = email.split('@');
  if (!domain) return email;
  
  const visibleChars = Math.min(2, Math.floor(localPart.length / 2));
  const hiddenLength = localPart.length - visibleChars;
  const redacted = localPart.slice(0, visibleChars) + '*'.repeat(hiddenLength);
  
  return `${redacted}@${domain}`;
};

// Redact sensitive order data for sharing
export interface OrderData {
  id: string;
  customerName?: string;
  customerPhone?: string;
  customerEmail?: string;
  paymentMethod?: string;
  cardNumber?: string;
  totalAmount: number;
  items: any[];
  notes?: string;
}

export const redactOrderForSharing = (order: OrderData): OrderData => {
  return {
    ...order,
    customerName: order.customerName ? `${order.customerName.charAt(0)}***` : undefined,
    customerPhone: order.customerPhone ? redactPhoneNumber(order.customerPhone) : undefined,
    customerEmail: order.customerEmail ? redactEmail(order.customerEmail) : undefined,
    cardNumber: order.cardNumber ? redactCardNumber(order.cardNumber) : undefined,
    // Remove sensitive notes that might contain PII
    notes: order.notes?.replace(/\b\d{3,}\b/g, '***'), // Redact numbers with 3+ digits
  };
};

// Check if data contains sensitive information
export const containsSensitiveData = (text: string): boolean => {
  // Check for common patterns
  const patterns = [
    /\b\d{13,19}\b/, // Credit card numbers
    /\b\d{3}-\d{2}-\d{4}\b/, // SSN format
    /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/, // Email
    /\b\d{10,11}\b/, // Phone numbers
  ];
  
  return patterns.some(pattern => pattern.test(text));
};

// Generate safe export data
export const generateSafeExportData = (data: any): string => {
  const safeData = JSON.parse(JSON.stringify(data)); // Deep clone
  
  // Recursively redact sensitive fields
  const sensitiveFields = ['cardNumber', 'cvv', 'ssn', 'password', 'token', 'secret'];
  
  const redactObject = (obj: any) => {
    for (const key in obj) {
      if (sensitiveFields.some(field => key.toLowerCase().includes(field))) {
        obj[key] = '***REDACTED***';
      } else if (typeof obj[key] === 'object' && obj[key] !== null) {
        redactObject(obj[key]);
      } else if (typeof obj[key] === 'string' && containsSensitiveData(obj[key])) {
        obj[key] = '***POTENTIALLY_SENSITIVE***';
      }
    }
  };
  
  redactObject(safeData);
  return JSON.stringify(safeData, null, 2);
};