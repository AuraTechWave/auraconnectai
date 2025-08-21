import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import { Button } from '../Button';

// Mock vector icons
jest.mock('react-native-vector-icons/MaterialCommunityIcons', () => 'Icon');

describe('Button', () => {
  it('renders with title', () => {
    const { getByText } = render(<Button title="Test Button" />);
    expect(getByText('Test Button')).toBeTruthy();
  });

  it('handles onPress event', () => {
    const onPress = jest.fn();
    const { getByText } = render(
      <Button title="Press Me" onPress={onPress} />
    );

    fireEvent.press(getByText('Press Me'));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('renders with different variants', () => {
    const variants = ['primary', 'secondary', 'tertiary', 'danger', 'ghost', 'outline'] as const;
    
    variants.forEach(variant => {
      const { getByText } = render(
        <Button title={`${variant} Button`} variant={variant} />
      );
      expect(getByText(`${variant} Button`)).toBeTruthy();
    });
  });

  it('renders with different sizes', () => {
    const sizes = ['small', 'medium', 'large'] as const;
    
    sizes.forEach(size => {
      const { getByText } = render(
        <Button title={`${size} Button`} size={size} />
      );
      expect(getByText(`${size} Button`)).toBeTruthy();
    });
  });

  it('renders with icon', () => {
    const { getByText, UNSAFE_getByType } = render(
      <Button title="Icon Button" icon="check" />
    );
    
    expect(getByText('Icon Button')).toBeTruthy();
    expect(UNSAFE_getByType('Icon')).toBeTruthy();
  });

  it('renders with icon on right', () => {
    const { getByText, UNSAFE_getAllByType } = render(
      <Button title="Icon Right" icon="arrow-right" iconPosition="right" />
    );
    
    expect(getByText('Icon Right')).toBeTruthy();
    const icons = UNSAFE_getAllByType('Icon');
    expect(icons.length).toBe(1);
  });

  it('shows loading state', () => {
    const { queryByText, getByTestId } = render(
      <Button title="Loading Button" loading={true} />
    );
    
    // Title should not be visible when loading
    expect(queryByText('Loading Button')).toBeFalsy();
    // ActivityIndicator should be present
    expect(() => getByTestId('button-loading')).not.toThrow();
  });

  it('disables button when disabled prop is true', () => {
    const onPress = jest.fn();
    const { getByText } = render(
      <Button title="Disabled Button" disabled={true} onPress={onPress} />
    );

    fireEvent.press(getByText('Disabled Button'));
    expect(onPress).not.toHaveBeenCalled();
  });

  it('disables button when loading', () => {
    const onPress = jest.fn();
    const { getByTestId } = render(
      <Button title="Loading" loading={true} onPress={onPress} testID="loading-button" />
    );

    fireEvent.press(getByTestId('loading-button'));
    expect(onPress).not.toHaveBeenCalled();
  });

  it('renders full width button', () => {
    const { getByText } = render(
      <Button title="Full Width" fullWidth={true} />
    );
    
    const button = getByText('Full Width').parent;
    expect(button?.props.style).toMatchObject(
      expect.objectContaining({
        width: '100%',
      })
    );
  });

  it('applies custom styles', () => {
    const customStyle = { backgroundColor: 'red' };
    const customTextStyle = { fontSize: 20 };
    
    const { getByText } = render(
      <Button 
        title="Custom Style" 
        style={customStyle}
        textStyle={customTextStyle}
      />
    );
    
    expect(getByText('Custom Style')).toBeTruthy();
  });

  it('has correct accessibility props', () => {
    const { getByRole, getByLabelText } = render(
      <Button 
        title="Accessible Button" 
        accessibilityLabel="Custom Label"
        accessibilityHint="Custom Hint"
      />
    );
    
    expect(getByRole('button')).toBeTruthy();
    expect(getByLabelText('Custom Label')).toBeTruthy();
  });

  it('shows busy state when loading', () => {
    const { getByRole } = render(
      <Button title="Loading" loading={true} />
    );
    
    const button = getByRole('button');
    expect(button.props.accessibilityState).toMatchObject({
      disabled: false,
      busy: true,
    });
  });
});