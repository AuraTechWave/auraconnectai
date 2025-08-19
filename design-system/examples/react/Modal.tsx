import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import FocusTrap from 'focus-trap-react';
import modalSpec from '@auraconnect/design-system/components/modal.json';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  size?: 'small' | 'medium' | 'large' | 'fullscreen';
  closeOnBackdropClick?: boolean;
  closeOnEscape?: boolean;
  'aria-labelledby'?: string;
  'aria-describedby'?: string;
}

export const Modal: React.FC<ModalProps> = ({
  open,
  onClose,
  title,
  children,
  size = 'medium',
  closeOnBackdropClick = true,
  closeOnEscape = true,
  'aria-labelledby': ariaLabelledby,
  'aria-describedby': ariaDescribedby,
}) => {
  const [mounted, setMounted] = useState(false);
  const previousActiveElement = useRef<HTMLElement | null>(null);
  const titleId = useRef(`modal-title-${Math.random().toString(36).substr(2, 9)}`);
  const descId = useRef(`modal-desc-${Math.random().toString(36).substr(2, 9)}`);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  useEffect(() => {
    if (open) {
      // Store currently focused element
      previousActiveElement.current = document.activeElement as HTMLElement;
      
      // Prevent body scroll
      document.body.style.overflow = 'hidden';
      
      // Handle escape key
      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === 'Escape' && closeOnEscape) {
          onClose();
        }
      };
      
      document.addEventListener('keydown', handleEscape);
      
      return () => {
        document.removeEventListener('keydown', handleEscape);
        document.body.style.overflow = '';
        
        // Restore focus to previous element
        if (previousActiveElement.current && previousActiveElement.current.focus) {
          previousActiveElement.current.focus();
        }
      };
    }
  }, [open, onClose, closeOnEscape]);

  if (!mounted || !open) return null;

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget && closeOnBackdropClick) {
      onClose();
    }
  };

  const modalContent = (
    <FocusTrap
      active={open}
      focusTrapOptions={{
        initialFocus: false,
        allowOutsideClick: true,
        returnFocusOnDeactivate: true,
      }}
    >
      <div
        className="aura-modal__backdrop"
        onClick={handleBackdropClick}
        aria-hidden="true"
      >
        <div
          className={`aura-modal__container aura-modal__container--${size}`}
          role="dialog"
          aria-modal="true"
          aria-labelledby={ariaLabelledby || (title ? titleId.current : undefined)}
          aria-describedby={ariaDescribedby || descId.current}
        >
          <div className="aura-modal__content">
            {title && (
              <div className="aura-modal__header">
                <h2 id={titleId.current} className="aura-modal__title">
                  {title}
                </h2>
                <button
                  className="aura-modal__close"
                  onClick={onClose}
                  aria-label="Close dialog"
                  type="button"
                >
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            )}
            <div id={descId.current} className="aura-modal__body">
              {children}
            </div>
          </div>
        </div>
      </div>
    </FocusTrap>
  );

  return createPortal(modalContent, document.body);
};

// CSS for the modal
export const modalStyles = `
.aura-modal__backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(42, 53, 71, 0.6);
  backdrop-filter: blur(4px);
  z-index: 1100;
  animation: fadeIn var(--animations-duration-fast) var(--animations-easing-easeOut);
}

.aura-modal__container {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  max-width: 90vw;
  max-height: 90vh;
  width: 100%;
  z-index: 1101;
  animation: slideUp var(--animations-duration-normal) var(--animations-easing-easeOut);
}

.aura-modal__container--small {
  max-width: 400px;
}

.aura-modal__container--medium {
  max-width: 600px;
}

.aura-modal__container--large {
  max-width: 900px;
}

.aura-modal__container--fullscreen {
  max-width: 100vw;
  max-height: 100vh;
  width: 100vw;
  height: 100vh;
}

.aura-modal__content {
  background: var(--colors-semantic-surface-card);
  border-radius: var(--borders-radius-lg);
  box-shadow: var(--shadows-elevation-8);
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  overflow: hidden;
}

.aura-modal__container--fullscreen .aura-modal__content {
  border-radius: 0;
  max-height: 100vh;
}

.aura-modal__header {
  padding: var(--spacing-component-padding-lg);
  border-bottom: 1px solid var(--colors-semantic-border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-component-gap-md);
  flex-shrink: 0;
}

.aura-modal__title {
  font-size: var(--typography-fontSize-xl);
  font-weight: var(--typography-fontWeight-semibold);
  line-height: var(--typography-lineHeight-tight);
  color: var(--colors-semantic-text-primary);
  margin: 0;
}

.aura-modal__close {
  width: 32px;
  height: 32px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: var(--borders-radius-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--colors-semantic-text-secondary);
  transition: var(--animations-transition-fast);
}

.aura-modal__close:hover {
  background: var(--colors-semantic-surface-hover);
  color: var(--colors-semantic-text-primary);
}

.aura-modal__close:focus-visible {
  outline: none;
  box-shadow: var(--shadows-focus-primary);
}

.aura-modal__body {
  padding: var(--spacing-component-padding-lg);
  overflow-y: auto;
  flex: 1;
  color: var(--colors-semantic-text-primary);
}

/* Animations */
@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translate(-50%, -40%);
  }
  to {
    opacity: 1;
    transform: translate(-50%, -50%);
  }
}

/* Mobile responsive */
@media (max-width: 640px) {
  .aura-modal__container {
    margin: var(--spacing-component-margin-md);
    max-width: calc(100vw - 32px);
    max-height: calc(100vh - 32px);
  }
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .aura-modal__backdrop,
  .aura-modal__container {
    animation: none;
  }
}

/* Dark theme adjustments handled automatically via CSS variables */
[data-theme="dark"] .aura-modal__backdrop {
  background: rgba(0, 0, 0, 0.8);
}
`;