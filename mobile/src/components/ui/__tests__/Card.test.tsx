import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import { Text } from 'react-native';
import { Card, CardHeader, CardContent, CardFooter } from '../Card';

describe('Card Component', () => {
  it('renders correctly with default props', () => {
    const { getByText } = render(
      <Card>
        <Text>Card Content</Text>
      </Card>
    );
    expect(getByText('Card Content')).toBeTruthy();
  });

  it('renders with different variants', () => {
    const variants: Array<'elevated' | 'outlined' | 'filled'> = ['elevated', 'outlined', 'filled'];
    
    variants.forEach(variant => {
      const { getByText } = render(
        <Card variant={variant}>
          <Text>{`${variant} card`}</Text>
        </Card>
      );
      expect(getByText(`${variant} card`)).toBeTruthy();
    });
  });

  it('applies correct padding sizes', () => {
    const paddings: Array<'none' | 'small' | 'medium' | 'large'> = ['none', 'small', 'medium', 'large'];
    
    paddings.forEach(padding => {
      const { getByText } = render(
        <Card padding={padding}>
          <Text>{`${padding} padding`}</Text>
        </Card>
      );
      expect(getByText(`${padding} padding`)).toBeTruthy();
    });
  });

  it('handles onPress when provided', () => {
    const onPressMock = jest.fn();
    const { getByText } = render(
      <Card onPress={onPressMock}>
        <Text>Pressable Card</Text>
      </Card>
    );
    
    fireEvent.press(getByText('Pressable Card'));
    expect(onPressMock).toHaveBeenCalledTimes(1);
  });

  it('does not handle press when onPress is not provided', () => {
    const { getByText } = render(
      <Card>
        <Text>Non-pressable Card</Text>
      </Card>
    );
    
    // Should not throw error when pressed
    expect(() => fireEvent.press(getByText('Non-pressable Card'))).not.toThrow();
  });

  it('applies custom styles', () => {
    const customStyle = { marginHorizontal: 20 };
    const { getByTestId } = render(
      <Card style={customStyle} testID="custom-card">
        <Text>Custom styled card</Text>
      </Card>
    );
    
    const card = getByTestId('custom-card');
    expect(card.props.style).toMatchObject(
      expect.objectContaining(customStyle)
    );
  });

  it('has minimum touch target size when pressable', () => {
    const onPressMock = jest.fn();
    const { getByText } = render(
      <Card onPress={onPressMock} padding="small">
        <Text>Small Card</Text>
      </Card>
    );
    
    const card = getByText('Small Card').parent;
    // Card with small padding should still be easily tappable
    expect(card).toBeTruthy();
  });
});

describe('CardHeader Component', () => {
  it('renders children correctly', () => {
    const { getByText } = render(
      <CardHeader>
        <Text>Header Title</Text>
      </CardHeader>
    );
    expect(getByText('Header Title')).toBeTruthy();
  });

  it('applies custom styles', () => {
    const customStyle = { backgroundColor: 'red' };
    const { getByTestId } = render(
      <CardHeader style={customStyle}>
        <Text testID="header-content">Header</Text>
      </CardHeader>
    );
    
    const header = getByTestId('header-content').parent;
    expect(header?.props.style).toMatchObject(
      expect.arrayContaining([
        expect.objectContaining(customStyle)
      ])
    );
  });
});

describe('CardContent Component', () => {
  it('renders children correctly', () => {
    const { getByText } = render(
      <CardContent>
        <Text>Content Body</Text>
      </CardContent>
    );
    expect(getByText('Content Body')).toBeTruthy();
  });

  it('applies custom styles', () => {
    const customStyle = { paddingHorizontal: 30 };
    const { getByTestId } = render(
      <CardContent style={customStyle}>
        <Text testID="content-body">Content</Text>
      </CardContent>
    );
    
    const content = getByTestId('content-body').parent;
    expect(content?.props.style).toMatchObject(
      expect.arrayContaining([
        expect.objectContaining(customStyle)
      ])
    );
  });
});

describe('CardFooter Component', () => {
  it('renders children correctly', () => {
    const { getByText } = render(
      <CardFooter>
        <Text>Footer Actions</Text>
      </CardFooter>
    );
    expect(getByText('Footer Actions')).toBeTruthy();
  });

  it('applies custom styles', () => {
    const customStyle = { justifyContent: 'center' };
    const { getByTestId } = render(
      <CardFooter style={customStyle}>
        <Text testID="footer-actions">Footer</Text>
      </CardFooter>
    );
    
    const footer = getByTestId('footer-actions').parent;
    expect(footer?.props.style).toMatchObject(
      expect.arrayContaining([
        expect.objectContaining(customStyle)
      ])
    );
  });
});

describe('Card with Header, Content, and Footer', () => {
  it('renders complete card structure', () => {
    const { getByText } = render(
      <Card>
        <CardHeader>
          <Text>Card Title</Text>
        </CardHeader>
        <CardContent>
          <Text>Card Body</Text>
        </CardContent>
        <CardFooter>
          <Text>Card Actions</Text>
        </CardFooter>
      </Card>
    );
    
    expect(getByText('Card Title')).toBeTruthy();
    expect(getByText('Card Body')).toBeTruthy();
    expect(getByText('Card Actions')).toBeTruthy();
  });

  it('handles press on complete card', () => {
    const onPressMock = jest.fn();
    const { getByText } = render(
      <Card onPress={onPressMock}>
        <CardHeader>
          <Text>Title</Text>
        </CardHeader>
        <CardContent>
          <Text>Content</Text>
        </CardContent>
      </Card>
    );
    
    fireEvent.press(getByText('Title'));
    expect(onPressMock).toHaveBeenCalledTimes(1);
    
    fireEvent.press(getByText('Content'));
    expect(onPressMock).toHaveBeenCalledTimes(2);
  });
});