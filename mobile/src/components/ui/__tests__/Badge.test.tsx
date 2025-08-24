import React from 'react';
import { render } from '@testing-library/react-native';
import { Badge, BadgeContainer } from '../Badge';

describe('Badge Component', () => {
  describe('Badge', () => {
    it('renders correctly with default props', () => {
      const { getByText } = render(<Badge>Default Badge</Badge>);
      expect(getByText('Default Badge')).toBeTruthy();
    });

    it('renders with primary variant', () => {
      const { getByText } = render(
        <Badge variant="primary">Primary Badge</Badge>
      );
      expect(getByText('Primary Badge')).toBeTruthy();
    });

    it('renders with secondary variant', () => {
      const { getByText } = render(
        <Badge variant="secondary">Secondary Badge</Badge>
      );
      expect(getByText('Secondary Badge')).toBeTruthy();
    });

    it('renders with success variant', () => {
      const { getByText } = render(
        <Badge variant="success">Success Badge</Badge>
      );
      expect(getByText('Success Badge')).toBeTruthy();
    });

    it('renders with warning variant', () => {
      const { getByText } = render(
        <Badge variant="warning">Warning Badge</Badge>
      );
      expect(getByText('Warning Badge')).toBeTruthy();
    });

    it('renders with error variant', () => {
      const { getByText } = render(
        <Badge variant="error">Error Badge</Badge>
      );
      expect(getByText('Error Badge')).toBeTruthy();
    });

    it('renders with info variant', () => {
      const { getByText } = render(
        <Badge variant="info">Info Badge</Badge>
      );
      expect(getByText('Info Badge')).toBeTruthy();
    });

    it('renders different sizes correctly', () => {
      const sizes = ['small', 'medium', 'large'] as const;
      
      sizes.forEach(size => {
        const { getByText } = render(
          <Badge size={size}>{size} Badge</Badge>
        );
        expect(getByText(`${size} Badge`)).toBeTruthy();
      });
    });

    it('renders with custom styles', () => {
      const customStyle = { backgroundColor: 'purple' };
      const { getByText } = render(
        <Badge style={customStyle}>Custom Badge</Badge>
      );
      expect(getByText('Custom Badge')).toBeTruthy();
    });

    it('renders with pill shape', () => {
      const { getByTestId } = render(
        <Badge pill testID="badge">Pill Badge</Badge>
      );
      expect(getByTestId('badge')).toBeTruthy();
    });

    it('renders with icon', () => {
      const { getByTestId } = render(
        <Badge icon="check" testID="badge">Icon Badge</Badge>
      );
      expect(getByTestId('badge')).toBeTruthy();
    });
  });

  describe('BadgeContainer', () => {
    it('renders children correctly', () => {
      const { getByText } = render(
        <BadgeContainer>
          <Badge>Badge 1</Badge>
          <Badge>Badge 2</Badge>
        </BadgeContainer>
      );
      expect(getByText('Badge 1')).toBeTruthy();
      expect(getByText('Badge 2')).toBeTruthy();
    });

    it('renders with custom styles', () => {
      const customStyle = { backgroundColor: 'lightgray' };
      const { getByTestId } = render(
        <BadgeContainer style={customStyle} testID="container">
          <Badge>Badge</Badge>
        </BadgeContainer>
      );
      expect(getByTestId('container')).toBeTruthy();
    });

    it('renders with gap prop', () => {
      const { getByTestId } = render(
        <BadgeContainer gap={20} testID="container">
          <Badge>Badge 1</Badge>
          <Badge>Badge 2</Badge>
        </BadgeContainer>
      );
      expect(getByTestId('container')).toBeTruthy();
    });

    it('renders with wrap prop', () => {
      const { getByTestId } = render(
        <BadgeContainer wrap testID="container">
          <Badge>Badge 1</Badge>
          <Badge>Badge 2</Badge>
          <Badge>Badge 3</Badge>
        </BadgeContainer>
      );
      expect(getByTestId('container')).toBeTruthy();
    });
  });
});