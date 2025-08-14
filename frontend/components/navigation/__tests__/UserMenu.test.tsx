/**
 * UserMenu Component Tests
 * 
 * Tests for edge cases in getUserInitials function
 */

import { renderHook } from '@testing-library/react';

// Test utility function that mirrors the getUserInitials logic
const getUserInitials = (user: { email?: string; name?: string }) => {
  if (!user.email) return '?';
  
  // If user has a name, use that for initials
  if (user.name) {
    const nameParts = user.name.trim().split(/\s+/).filter(part => part.length > 0);
    if (nameParts.length >= 2) {
      return (nameParts[0][0] + nameParts[1][0]).toUpperCase();
    } else if (nameParts.length === 1 && nameParts[0].length > 0) {
      return nameParts[0].substring(0, 2).toUpperCase();
    }
  }
  
  // Fall back to email-based initials
  const emailLocal = user.email.split('@')[0];
  
  // Remove leading/trailing periods and split by period
  const parts = emailLocal.split('.').filter(part => part.length > 0);
  
  if (parts.length >= 2) {
    // Use first character of first two non-empty parts
    return (parts[0][0] + parts[1][0]).toUpperCase();
  } else if (parts.length === 1) {
    // Use first two characters of the single part, or just one if it's short
    const part = parts[0];
    return part.length >= 2 ? part.substring(0, 2).toUpperCase() : part[0].toUpperCase();
  }
  
  // Final fallback: use first valid character from email
  for (let i = 0; i < emailLocal.length; i++) {
    if (/[a-zA-Z0-9]/.test(emailLocal[i])) {
      return emailLocal[i].toUpperCase();
    }
  }
  
  return '?';
};

describe('UserMenu - getUserInitials', () => {
  describe('Name-based initials', () => {
    test('should use first and last name initials when full name is provided', () => {
      expect(getUserInitials({ 
        email: 'test@example.com', 
        name: 'John Doe' 
      })).toBe('JD');
    });

    test('should use first two letters of single name', () => {
      expect(getUserInitials({ 
        email: 'test@example.com', 
        name: 'John' 
      })).toBe('JO');
    });

    test('should handle names with extra spaces', () => {
      expect(getUserInitials({ 
        email: 'test@example.com', 
        name: '  John   Doe  ' 
      })).toBe('JD');
    });

    test('should handle three-part names', () => {
      expect(getUserInitials({ 
        email: 'test@example.com', 
        name: 'John Paul Smith' 
      })).toBe('JP');
    });
  });

  describe('Email-based initials', () => {
    test('should handle normal email format', () => {
      expect(getUserInitials({ 
        email: 'john.doe@example.com' 
      })).toBe('JD');
    });

    test('should handle email without dots', () => {
      expect(getUserInitials({ 
        email: 'johndoe@example.com' 
      })).toBe('JO');
    });

    test('should handle email starting with period', () => {
      expect(getUserInitials({ 
        email: '.john.doe@example.com' 
      })).toBe('JD');
    });

    test('should handle email with consecutive periods', () => {
      expect(getUserInitials({ 
        email: 'john..doe@example.com' 
      })).toBe('JD');
    });

    test('should handle email with only periods before @', () => {
      expect(getUserInitials({ 
        email: '...@example.com' 
      })).toBe('?');
    });

    test('should handle single character email', () => {
      expect(getUserInitials({ 
        email: 'j@example.com' 
      })).toBe('J');
    });

    test('should handle email with numbers', () => {
      expect(getUserInitials({ 
        email: 'john123@example.com' 
      })).toBe('JO');
    });

    test('should use first valid alphanumeric character for special emails', () => {
      expect(getUserInitials({ 
        email: '---test@example.com' 
      })).toBe('T');
    });

    test('should handle email with underscores', () => {
      expect(getUserInitials({ 
        email: 'john_doe@example.com' 
      })).toBe('JO');
    });

    test('should handle email with hyphens', () => {
      expect(getUserInitials({ 
        email: 'john-doe@example.com' 
      })).toBe('JO');
    });
  });

  describe('Edge cases', () => {
    test('should return ? for missing email', () => {
      expect(getUserInitials({})).toBe('?');
    });

    test('should return ? for empty email', () => {
      expect(getUserInitials({ email: '' })).toBe('?');
    });

    test('should handle email with only special characters', () => {
      expect(getUserInitials({ 
        email: '!@#$%^&*@example.com' 
      })).toBe('?');
    });

    test('should prioritize name over email', () => {
      expect(getUserInitials({ 
        email: 'test@example.com',
        name: 'Alice Bob'
      })).toBe('AB');
    });

    test('should handle empty name string', () => {
      expect(getUserInitials({ 
        email: 'john.doe@example.com',
        name: ''
      })).toBe('JD');
    });

    test('should handle whitespace-only name', () => {
      expect(getUserInitials({ 
        email: 'john.doe@example.com',
        name: '   '
      })).toBe('JD');
    });
  });
});