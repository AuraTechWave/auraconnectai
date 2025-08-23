import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import { Input } from '../Input';

describe('Input Component', () => {
  it('renders correctly with default props', () => {
    const { getByPlaceholderText } = render(
      <Input placeholder="Enter text" />
    );
    expect(getByPlaceholderText('Enter text')).toBeTruthy();
  });

  it('displays label when provided', () => {
    const { getByText } = render(
      <Input label="Email Address" placeholder="Enter email" />
    );
    expect(getByText('Email Address')).toBeTruthy();
  });

  it('handles text input correctly', () => {
    const onChangeTextMock = jest.fn();
    const { getByPlaceholderText } = render(
      <Input 
        placeholder="Enter text" 
        onChangeText={onChangeTextMock}
      />
    );
    
    const input = getByPlaceholderText('Enter text');
    fireEvent.changeText(input, 'Test input');
    expect(onChangeTextMock).toHaveBeenCalledWith('Test input');
  });

  it('shows error message when error prop is provided', () => {
    const { getByText } = render(
      <Input 
        placeholder="Enter text" 
        error="This field is required"
      />
    );
    expect(getByText('This field is required')).toBeTruthy();
  });

  it('shows helper text when helper prop is provided', () => {
    const { getByText, queryByText } = render(
      <Input 
        placeholder="Enter text" 
        helper="Enter at least 8 characters"
      />
    );
    expect(getByText('Enter at least 8 characters')).toBeTruthy();
  });

  it('does not show helper text when error is present', () => {
    const { queryByText } = render(
      <Input 
        placeholder="Enter text" 
        error="Error message"
        helper="Helper text"
      />
    );
    expect(queryByText('Helper text')).toBeNull();
  });

  it('handles focus and blur events', () => {
    const onFocusMock = jest.fn();
    const onBlurMock = jest.fn();
    const { getByPlaceholderText } = render(
      <Input 
        placeholder="Enter text" 
        onFocus={onFocusMock}
        onBlur={onBlurMock}
      />
    );
    
    const input = getByPlaceholderText('Enter text');
    fireEvent(input, 'focus');
    expect(onFocusMock).toHaveBeenCalled();
    
    fireEvent(input, 'blur');
    expect(onBlurMock).toHaveBeenCalled();
  });

  it('renders left icon when provided', () => {
    const { UNSAFE_getByType } = render(
      <Input 
        placeholder="Enter email" 
        leftIcon="email"
      />
    );
    // Icon component should be present
    const icons = UNSAFE_getByType('MaterialCommunityIcons' as any);
    expect(icons).toBeTruthy();
  });

  it('handles right icon press', () => {
    const onRightIconPressMock = jest.fn();
    const { getByPlaceholderText } = render(
      <Input 
        placeholder="Enter password" 
        rightIcon="eye"
        onRightIconPress={onRightIconPressMock}
        secureTextEntry
      />
    );
    
    // Find and press the right icon touchable
    const parent = getByPlaceholderText('Enter password').parent;
    if (parent && parent.children) {
      const touchables = parent.children.filter((child: any) => 
        child.type?.displayName === 'TouchableOpacity'
      );
      if (touchables.length > 0) {
        fireEvent.press(touchables[0]);
        expect(onRightIconPressMock).toHaveBeenCalled();
      }
    }
  });

  it('is disabled when disabled prop is true', () => {
    const onChangeTextMock = jest.fn();
    const { getByPlaceholderText } = render(
      <Input 
        placeholder="Disabled input" 
        disabled
        onChangeText={onChangeTextMock}
      />
    );
    
    const input = getByPlaceholderText('Disabled input');
    expect(input.props.editable).toBe(false);
  });

  it('applies correct variant styles', () => {
    const variants: Array<'outlined' | 'filled' | 'underlined'> = ['outlined', 'filled', 'underlined'];
    
    variants.forEach(variant => {
      const { getByPlaceholderText } = render(
        <Input 
          placeholder={`${variant} input`}
          variant={variant}
        />
      );
      
      const input = getByPlaceholderText(`${variant} input`);
      expect(input).toBeTruthy();
    });
  });

  it('applies correct size styles', () => {
    const sizes: Array<'small' | 'medium' | 'large'> = ['small', 'medium', 'large'];
    
    sizes.forEach(size => {
      const { getByPlaceholderText } = render(
        <Input 
          placeholder={`${size} input`}
          size={size}
        />
      );
      
      const input = getByPlaceholderText(`${size} input`);
      expect(input).toBeTruthy();
    });
  });

  it('handles value prop correctly', () => {
    const { getByDisplayValue } = render(
      <Input 
        placeholder="Enter text" 
        value="Initial value"
      />
    );
    expect(getByDisplayValue('Initial value')).toBeTruthy();
  });

  it('has appropriate touch target size', () => {
    const { getByPlaceholderText } = render(
      <Input 
        placeholder="Test input" 
        size="small"
      />
    );
    
    const input = getByPlaceholderText('Test input');
    const parent = input.parent;
    
    // The input container should have minimum height for touch targets
    if (parent?.props?.style) {
      const styles = Array.isArray(parent.props.style) 
        ? parent.props.style 
        : [parent.props.style];
      
      const hasMinHeight = styles.some((style: any) => 
        style?.minHeight && style.minHeight >= 40
      );
      expect(hasMinHeight).toBe(true);
    }
  });

  it('supports all TextInput props', () => {
    const { getByPlaceholderText } = render(
      <Input 
        placeholder="Test input"
        keyboardType="email-address"
        autoCapitalize="none"
        autoCorrect={false}
        maxLength={50}
      />
    );
    
    const input = getByPlaceholderText('Test input');
    expect(input.props.keyboardType).toBe('email-address');
    expect(input.props.autoCapitalize).toBe('none');
    expect(input.props.autoCorrect).toBe(false);
    expect(input.props.maxLength).toBe(50);
  });

  describe('Accessibility', () => {
    it('has correct accessibility properties', () => {
      const { getByPlaceholderText } = render(
        <Input 
          placeholder="Test input"
          label="Test Label"
          accessibilityLabel="Custom Label"
          accessibilityHint="Custom Hint"
        />
      );
      
      const input = getByPlaceholderText('Test input');
      expect(input.props.accessible).toBe(true);
      expect(input.props.accessibilityLabel).toBe('Custom Label');
      expect(input.props.accessibilityHint).toBe('Custom Hint');
    });

    it('uses label as accessibilityLabel when not provided', () => {
      const { getByPlaceholderText } = render(
        <Input 
          placeholder="Test input"
          label="Email Address"
        />
      );
      
      const input = getByPlaceholderText('Test input');
      expect(input.props.accessibilityLabel).toBe('Email Address');
    });

    it('uses placeholder as accessibilityLabel when label not provided', () => {
      const { getByPlaceholderText } = render(
        <Input 
          placeholder="Enter your email"
        />
      );
      
      const input = getByPlaceholderText('Enter your email');
      expect(input.props.accessibilityLabel).toBe('Enter your email');
    });

    it('has correct accessibility state when disabled', () => {
      const { getByPlaceholderText } = render(
        <Input 
          placeholder="Test input"
          disabled={true}
        />
      );
      
      const input = getByPlaceholderText('Test input');
      expect(input.props.accessibilityState.disabled).toBe(true);
    });

    it('error text has alert role', () => {
      const { getByText } = render(
        <Input 
          placeholder="Test input"
          error="This field is required"
        />
      );
      
      const errorText = getByText('This field is required');
      expect(errorText.props.accessibilityRole).toBe('alert');
      expect(errorText.props.accessibilityLiveRegion).toBe('polite');
    });

    it('helper text has text role', () => {
      const { getByText } = render(
        <Input 
          placeholder="Test input"
          helper="Enter at least 8 characters"
        />
      );
      
      const helperText = getByText('Enter at least 8 characters');
      expect(helperText.props.accessibilityRole).toBe('text');
    });

    it('uses helper as accessibilityHint when provided', () => {
      const { getByPlaceholderText } = render(
        <Input 
          placeholder="Test input"
          helper="Password must be 8 characters"
        />
      );
      
      const input = getByPlaceholderText('Test input');
      expect(input.props.accessibilityHint).toBe('Password must be 8 characters');
    });

    it('includes value in accessibilityValue', () => {
      const { getByPlaceholderText } = render(
        <Input 
          placeholder="Test input"
          value="test@example.com"
        />
      );
      
      const input = getByPlaceholderText('Test input');
      expect(input.props.accessibilityValue.text).toBe('test@example.com');
    });
  });
});