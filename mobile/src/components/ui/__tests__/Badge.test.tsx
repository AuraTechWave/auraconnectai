import React from 'react';
import { render } from '@testing-library/react-native';
import { Badge, BadgeContainer } from '../Badge';

describe('Badge', () => {
  it('renders with label', () => {
    const { getByText } = render(<Badge label="New" />);
    expect(getByText('New')).toBeTruthy();
  });

  it('renders with number label', () => {
    const { getByText } = render(<Badge label={42} />);
    expect(getByText('42')).toBeTruthy();
  });

  it('renders with different variants', () => {
    const variants = ['default', 'primary', 'secondary', 'success', 'warning', 'error', 'info'] as const;
    
    variants.forEach(variant => {
      const { getByText } = render(
        <Badge label={variant} variant={variant} />
      );
      expect(getByText(variant)).toBeTruthy();
    });
  });

  it('renders with different sizes', () => {
    const sizes = ['small', 'medium', 'large'] as const;
    
    sizes.forEach(size => {
      const { getByText } = render(
        <Badge label={size} size={size} />
      );
      expect(getByText(size)).toBeTruthy();
    });
  });

  it('renders as dot when dot prop is true', () => {
    const { queryByText, getByRole } = render(
      <Badge label="Hidden" dot={true} />
    );
    
    // Label should not be visible
    expect(queryByText('Hidden')).toBeFalsy();
    // Dot should be rendered
    expect(getByRole('none')).toBeTruthy();
  });

  it('applies custom styles', () => {
    const customStyle = { backgroundColor: 'red' };
    const customTextStyle = { fontSize: 20 };
    
    const { getByText } = render(
      <Badge 
        label="Custom" 
        style={customStyle}
        textStyle={customTextStyle}
      />
    );
    
    expect(getByText('Custom')).toBeTruthy();
  });

  it('has correct accessibility props', () => {
    const { getByRole, getByLabelText } = render(
      <Badge 
        label="Important" 
        accessibilityLabel="Important notification"
      />
    );
    
    expect(getByRole('text')).toBeTruthy();
    expect(getByLabelText('Important notification')).toBeTruthy();
  });

  it('uses label as default accessibility label', () => {
    const { getByLabelText } = render(
      <Badge label="Alert" />
    );
    
    expect(getByLabelText('Alert')).toBeTruthy();
  });

  it('has correct accessibility for dot variant', () => {
    const { getByLabelText } = render(
      <Badge 
        label="Dot" 
        dot={true}
        variant="error"
        accessibilityLabel="Error indicator"
      />
    );
    
    expect(getByLabelText('Error indicator')).toBeTruthy();
  });
});

describe('BadgeContainer', () => {
  it('renders children with badge', () => {
    const { getByText } = render(
      <BadgeContainer badge={<Badge label="5" />}>
        <text>Content</text>
      </BadgeContainer>
    );
    
    expect(getByText('Content')).toBeTruthy();
    expect(getByText('5')).toBeTruthy();
  });

  it('renders children without badge', () => {
    const { getByText, queryByText } = render(
      <BadgeContainer>
        <text>Content</text>
      </BadgeContainer>
    );
    
    expect(getByText('Content')).toBeTruthy();
    expect(queryByText('Badge')).toBeFalsy();
  });

  it('positions badge correctly', () => {
    const positions = ['top-left', 'top-right', 'bottom-left', 'bottom-right'] as const;
    
    positions.forEach(position => {
      const { getByText } = render(
        <BadgeContainer 
          badge={<Badge label={position} />}
          position={position}
        >
          <text>Content</text>
        </BadgeContainer>
      );
      
      expect(getByText('Content')).toBeTruthy();
      expect(getByText(position)).toBeTruthy();
    });
  });

  it('defaults to top-right position', () => {
    const { getByText } = render(
      <BadgeContainer badge={<Badge label="Default" />}>
        <text>Content</text>
      </BadgeContainer>
    );
    
    expect(getByText('Default')).toBeTruthy();
  });
});