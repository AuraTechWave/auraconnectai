import React, { ButtonHTMLAttributes, forwardRef } from 'react';
import { tokens } from '@auraconnect/design-system';
import buttonSpec from '@auraconnect/design-system/components/button.json';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'contained' | 'outlined' | 'text';
  size?: 'small' | 'medium' | 'large';
  color?: 'primary' | 'secondary' | 'success' | 'warning' | 'error';
  startIcon?: React.ReactNode;
  endIcon?: React.ReactNode;
  fullWidth?: boolean;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'contained',
      size = 'medium',
      color = 'primary',
      startIcon,
      endIcon,
      fullWidth = false,
      loading = false,
      disabled = false,
      children,
      className,
      'aria-label': ariaLabel,
      ...props
    },
    ref
  ) => {
    // Get styles from spec
    const baseStyles = buttonSpec.button.variants[variant].styles.base;
    const sizeStyles = buttonSpec.button.sizes[size];
    const colorStyles = buttonSpec.button.colors[color][variant];
    const stateStyles = buttonSpec.button.variants[variant].styles.states;

    // Ensure accessibility
    const hasTextContent = React.Children.toArray(children).some(
      child => typeof child === 'string' || typeof child === 'number'
    );
    
    if (!hasTextContent && !ariaLabel) {
      console.warn('Button requires either text content or aria-label for accessibility');
    }

    return (
      <button
        ref={ref}
        className={`
          aura-button
          aura-button--${variant}
          aura-button--${size}
          aura-button--${color}
          ${fullWidth ? 'aura-button--full-width' : ''}
          ${loading ? 'aura-button--loading' : ''}
          ${className || ''}
        `.trim()}
        disabled={disabled || loading}
        aria-label={ariaLabel}
        aria-busy={loading}
        aria-disabled={disabled || loading}
        {...props}
      >
        {loading && (
          <span className="aura-button__loader" aria-hidden="true">
            <svg className="aura-spinner" viewBox="0 0 24 24">
              <circle
                className="aura-spinner__track"
                cx="12"
                cy="12"
                r="10"
                fill="none"
                strokeWidth="2"
              />
              <circle
                className="aura-spinner__head"
                cx="12"
                cy="12"
                r="10"
                fill="none"
                strokeWidth="2"
                strokeDasharray="31.416"
                strokeDashoffset="23.562"
              />
            </svg>
          </span>
        )}
        {startIcon && (
          <span className="aura-button__icon aura-button__icon--start" aria-hidden="true">
            {startIcon}
          </span>
        )}
        <span className="aura-button__content">{children}</span>
        {endIcon && (
          <span className="aura-button__icon aura-button__icon--end" aria-hidden="true">
            {endIcon}
          </span>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';

// CSS for the button (would be in a separate file)
export const buttonStyles = `
.aura-button {
  /* Base styles from tokens */
  border-radius: var(--borders-radius-md);
  font-family: var(--typography-fontFamily-primary);
  font-weight: var(--typography-fontWeight-semibold);
  letter-spacing: var(--typography-letterSpacing-wide);
  transition: var(--animations-transition-default);
  cursor: pointer;
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-component-gap-sm);
  white-space: nowrap;
  position: relative;
  overflow: hidden;
}

/* Focus styles for accessibility */
.aura-button:focus-visible {
  outline: none;
  box-shadow: var(--shadows-focus-primary);
}

/* Sizes */
.aura-button--small {
  padding: 6px 16px;
  font-size: var(--typography-fontSize-sm);
  min-height: 32px;
}

.aura-button--medium {
  padding: 8px 20px;
  font-size: var(--typography-fontSize-base);
  min-height: 40px;
}

.aura-button--large {
  padding: 12px 28px;
  font-size: var(--typography-fontSize-lg);
  min-height: 48px;
}

/* Variants */
.aura-button--contained {
  color: var(--colors-semantic-primary-contrast);
  background: var(--colors-semantic-primary-base);
}

.aura-button--contained:hover:not(:disabled) {
  background: var(--colors-semantic-primary-dark);
  transform: translateY(-1px);
  box-shadow: var(--shadows-elevation-2);
}

.aura-button--contained:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: var(--shadows-elevation-1);
}

.aura-button--outlined {
  background: transparent;
  border: 1px solid var(--colors-semantic-primary-base);
  color: var(--colors-semantic-primary-base);
}

.aura-button--outlined:hover:not(:disabled) {
  background: var(--colors-semantic-primary-light);
  border-color: var(--colors-semantic-primary-dark);
}

.aura-button--text {
  background: transparent;
  border: none;
  color: var(--colors-semantic-primary-base);
  padding: var(--spacing-component-padding-sm);
}

.aura-button--text:hover:not(:disabled) {
  background: var(--colors-semantic-primary-light);
}

/* Disabled state */
.aura-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* Loading state */
.aura-button--loading {
  color: transparent;
}

.aura-button__loader {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.aura-spinner {
  width: 20px;
  height: 20px;
  animation: spin 1s linear infinite;
}

.aura-spinner__track {
  stroke: var(--colors-semantic-primary-light);
}

.aura-spinner__head {
  stroke: currentColor;
  animation: dash 1.5s ease-in-out infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes dash {
  0% {
    stroke-dasharray: 1, 150;
    stroke-dashoffset: 0;
  }
  50% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -35;
  }
  100% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -124;
  }
}

/* Full width modifier */
.aura-button--full-width {
  width: 100%;
}

/* Color variants */
.aura-button--contained.aura-button--secondary {
  background: var(--colors-semantic-secondary-base);
  color: var(--colors-semantic-secondary-contrast);
}

.aura-button--contained.aura-button--success {
  background: var(--colors-semantic-success-base);
  color: var(--colors-semantic-success-contrast);
}

.aura-button--contained.aura-button--warning {
  background: var(--colors-semantic-warning-base);
  color: var(--colors-semantic-warning-contrast);
}

.aura-button--contained.aura-button--error {
  background: var(--colors-semantic-error-base);
  color: var(--colors-semantic-error-contrast);
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .aura-button {
    transition: none;
  }
  
  .aura-spinner {
    animation: none;
  }
}
`;