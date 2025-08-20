import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import { Button } from '../Button';

describe('Button Component', () => {
  it('renders correctly with default props', () => {
    const { getByText } = render(<Button>Test Button</Button>);
    expect(getByText('Test Button')).toBeTruthy();
  });

  it('calls onPress when pressed', () => {
    const onPressMock = jest.fn();
    const { getByText } = render(
      <Button onPress={onPressMock}>Press Me</Button>
    );
    
    fireEvent.press(getByText('Press Me'));
    expect(onPressMock).toHaveBeenCalledTimes(1);
  });

  it('shows loading state correctly', () => {
    const { getByTestId } = render(
      <Button loading testID="loading-button">
        Loading
      </Button>
    );
    
    const button = getByTestId('loading-button');
    expect(button.props.accessibilityState.busy).toBe(true);
  });

  it('is disabled when loading', () => {
    const onPressMock = jest.fn();
    const { getByText } = render(
      <Button loading onPress={onPressMock}>
        Loading Button
      </Button>
    );
    
    fireEvent.press(getByText('Loading Button'));
    expect(onPressMock).not.toHaveBeenCalled();
  });

  it('applies correct variant styles', () => {
    const { getByTestId, rerender } = render(
      <Button variant="primary" testID="button">
        Primary
      </Button>
    );
    
    let button = getByTestId('button');
    expect(button.props.style).toMatchObject(
      expect.objectContaining({
        backgroundColor: expect.any(String),
      })
    );
    
    rerender(
      <Button variant="outline" testID="button">
        Outline
      </Button>
    );
    
    button = getByTestId('button');
    expect(button.props.style).toMatchObject(
      expect.arrayContaining([
        expect.objectContaining({
          backgroundColor: 'transparent',
        }),
      ])
    );
  });

  it('applies correct size styles', () => {
    const { getByTestId, rerender } = render(
      <Button size="small" testID="button">
        Small
      </Button>
    );
    
    let button = getByTestId('button');
    expect(button.props.style).toMatchObject(
      expect.arrayContaining([
        expect.objectContaining({
          paddingVertical: expect.any(Number),
        }),
      ])
    );
    
    rerender(
      <Button size="large" testID="button">
        Large
      </Button>
    );
    
    button = getByTestId('button');
    expect(button.props.style).toMatchObject(
      expect.arrayContaining([
        expect.objectContaining({
          paddingVertical: expect.any(Number),
        }),
      ])
    );
  });

  it('renders with icon correctly', () => {
    const { getByTestId } = render(
      <Button icon="check" testID="button-with-icon">
        With Icon
      </Button>
    );
    
    expect(getByTestId('button-with-icon')).toBeTruthy();
  });

  it('has minimum touch target size', () => {
    const { getByTestId } = render(
      <Button size="small" testID="button">
        Small Button
      </Button>
    );
    
    const button = getByTestId('button');
    const styles = Array.isArray(button.props.style) 
      ? button.props.style 
      : [button.props.style];
    
    const heightStyle = styles.find(style => style?.minHeight);
    expect(heightStyle?.minHeight).toBeGreaterThanOrEqual(44);
  });

  it('has correct accessibility props', () => {
    const { getByTestId } = render(
      <Button 
        testID="accessible-button"
        accessibilityLabel="Custom Label"
        accessibilityHint="Custom Hint"
      >
        Accessible Button
      </Button>
    );
    
    const button = getByTestId('accessible-button');
    expect(button.props.accessible).toBe(true);
    expect(button.props.accessibilityRole).toBe('button');
    expect(button.props.accessibilityLabel).toBe('Custom Label');
    expect(button.props.accessibilityHint).toBe('Custom Hint');
  });

  it('handles disabled state correctly', () => {
    const onPressMock = jest.fn();
    const { getByTestId } = render(
      <Button disabled onPress={onPressMock} testID="disabled-button">
        Disabled
      </Button>
    );
    
    const button = getByTestId('disabled-button');
    fireEvent.press(button);
    
    expect(onPressMock).not.toHaveBeenCalled();
    expect(button.props.accessibilityState.disabled).toBe(true);
  });
});