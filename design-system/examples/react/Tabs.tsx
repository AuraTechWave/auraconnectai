import React, { useState, useRef, useEffect, KeyboardEvent } from 'react';
import tabsSpec from '@auraconnect/design-system/components/tabs.json';

interface Tab {
  id: string;
  label: string;
  content: React.ReactNode;
  disabled?: boolean;
  icon?: React.ReactNode;
  badge?: string | number;
}

interface TabsProps {
  tabs: Tab[];
  defaultTab?: string;
  variant?: 'standard' | 'pills' | 'vertical';
  size?: 'small' | 'medium' | 'large';
  onChange?: (tabId: string) => void;
  'aria-label'?: string;
}

export const Tabs: React.FC<TabsProps> = ({
  tabs,
  defaultTab,
  variant = 'standard',
  size = 'medium',
  onChange,
  'aria-label': ariaLabel,
}) => {
  const [activeTab, setActiveTab] = useState(defaultTab || tabs[0]?.id);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const tabListRef = useRef<HTMLDivElement>(null);

  // Find active tab index
  const activeIndex = tabs.findIndex(tab => tab.id === activeTab);
  const enabledTabs = tabs.filter(tab => !tab.disabled);

  useEffect(() => {
    // Focus the active tab when it changes via keyboard navigation
    if (tabRefs.current[focusedIndex]) {
      tabRefs.current[focusedIndex]?.focus();
    }
  }, [focusedIndex]);

  const handleTabClick = (tabId: string, index: number) => {
    const tab = tabs.find(t => t.id === tabId);
    if (tab && !tab.disabled) {
      setActiveTab(tabId);
      setFocusedIndex(index);
      onChange?.(tabId);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const isVertical = variant === 'vertical';
    let newIndex = focusedIndex;
    let handled = false;

    switch (e.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        if (!isVertical && e.key === 'ArrowDown') break;
        if (isVertical && e.key === 'ArrowRight') break;
        
        // Find next enabled tab
        newIndex = focusedIndex;
        do {
          newIndex = (newIndex + 1) % tabs.length;
        } while (tabs[newIndex].disabled && newIndex !== focusedIndex);
        
        handled = true;
        break;

      case 'ArrowLeft':
      case 'ArrowUp':
        if (!isVertical && e.key === 'ArrowUp') break;
        if (isVertical && e.key === 'ArrowLeft') break;
        
        // Find previous enabled tab
        newIndex = focusedIndex;
        do {
          newIndex = (newIndex - 1 + tabs.length) % tabs.length;
        } while (tabs[newIndex].disabled && newIndex !== focusedIndex);
        
        handled = true;
        break;

      case 'Home':
        // Find first enabled tab
        newIndex = tabs.findIndex(tab => !tab.disabled);
        handled = true;
        break;

      case 'End':
        // Find last enabled tab
        for (let i = tabs.length - 1; i >= 0; i--) {
          if (!tabs[i].disabled) {
            newIndex = i;
            break;
          }
        }
        handled = true;
        break;

      case 'Enter':
      case ' ':
        handleTabClick(tabs[focusedIndex].id, focusedIndex);
        handled = true;
        break;
    }

    if (handled) {
      e.preventDefault();
      setFocusedIndex(newIndex);
    }
  };

  const activeTabContent = tabs.find(tab => tab.id === activeTab)?.content;

  return (
    <div className={`aura-tabs aura-tabs--${variant} aura-tabs--${size}`}>
      <div
        ref={tabListRef}
        className="aura-tabs__list"
        role="tablist"
        aria-label={ariaLabel}
        onKeyDown={handleKeyDown}
      >
        {tabs.map((tab, index) => (
          <button
            key={tab.id}
            ref={el => tabRefs.current[index] = el}
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={tab.id === activeTab}
            aria-controls={`panel-${tab.id}`}
            aria-disabled={tab.disabled}
            tabIndex={index === focusedIndex ? 0 : -1}
            disabled={tab.disabled}
            className={`
              aura-tabs__tab
              ${tab.id === activeTab ? 'aura-tabs__tab--active' : ''}
              ${tab.disabled ? 'aura-tabs__tab--disabled' : ''}
            `.trim()}
            onClick={() => handleTabClick(tab.id, index)}
          >
            {tab.icon && (
              <span className="aura-tabs__icon" aria-hidden="true">
                {tab.icon}
              </span>
            )}
            <span className="aura-tabs__label">{tab.label}</span>
            {tab.badge !== undefined && (
              <span className="aura-tabs__badge" aria-label={`${tab.badge} items`}>
                {tab.badge}
              </span>
            )}
          </button>
        ))}
        {variant === 'standard' && (
          <div
            className="aura-tabs__indicator"
            style={{
              transform: `translateX(${activeIndex * 100}%)`,
              width: `${100 / tabs.length}%`,
            }}
            aria-hidden="true"
          />
        )}
      </div>
      
      {tabs.map(tab => (
        <div
          key={tab.id}
          role="tabpanel"
          id={`panel-${tab.id}`}
          aria-labelledby={`tab-${tab.id}`}
          hidden={tab.id !== activeTab}
          tabIndex={0}
          className="aura-tabs__panel"
        >
          {tab.id === activeTab && activeTabContent}
        </div>
      ))}
    </div>
  );
};

// CSS for tabs
export const tabsStyles = `
.aura-tabs {
  width: 100%;
}

.aura-tabs__list {
  display: flex;
  position: relative;
  min-height: 48px;
  margin: 0;
  padding: 0;
  list-style: none;
  align-items: stretch;
}

/* Standard variant */
.aura-tabs--standard .aura-tabs__list {
  border-bottom: 1px solid var(--colors-semantic-border-light);
}

.aura-tabs__tab {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-component-padding-md) var(--spacing-component-padding-lg);
  min-height: 48px;
  font-size: var(--typography-fontSize-base);
  font-weight: var(--typography-fontWeight-medium);
  color: var(--colors-semantic-text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: var(--animations-transition-fast);
  white-space: nowrap;
  text-decoration: none;
  gap: var(--spacing-component-gap-sm);
  flex: 1;
}

.aura-tabs__tab:hover:not(:disabled) {
  color: var(--colors-semantic-text-primary);
  background: var(--colors-semantic-surface-hover);
}

.aura-tabs__tab:focus-visible {
  outline: none;
  box-shadow: inset var(--shadows-focus-primary);
  z-index: 1;
}

.aura-tabs__tab--active {
  color: var(--colors-semantic-primary-base);
  font-weight: var(--typography-fontWeight-semibold);
}

.aura-tabs__tab--disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

.aura-tabs__icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.aura-tabs__badge {
  margin-left: var(--spacing-component-margin-sm);
  padding: 2px 6px;
  font-size: var(--typography-fontSize-xs);
  font-weight: var(--typography-fontWeight-semibold);
  border-radius: var(--borders-radius-full);
  background: var(--colors-semantic-primary-base);
  color: var(--colors-semantic-primary-contrast);
  min-width: 20px;
  text-align: center;
}

.aura-tabs__indicator {
  height: 2px;
  background: var(--colors-semantic-primary-base);
  position: absolute;
  bottom: 0;
  transition: var(--animations-transition-default);
}

/* Pills variant */
.aura-tabs--pills .aura-tabs__list {
  background: var(--colors-semantic-surface-subtle);
  padding: var(--spacing-component-padding-xs);
  border-radius: var(--borders-radius-lg);
  display: inline-flex;
  gap: var(--spacing-component-gap-xs);
  border-bottom: none;
}

.aura-tabs--pills .aura-tabs__tab {
  border-radius: var(--borders-radius-md);
  flex: unset;
}

.aura-tabs--pills .aura-tabs__tab--active {
  background: var(--colors-semantic-surface-card);
  box-shadow: var(--shadows-elevation-1);
}

/* Vertical variant */
.aura-tabs--vertical {
  display: flex;
}

.aura-tabs--vertical .aura-tabs__list {
  flex-direction: column;
  border-right: 1px solid var(--colors-semantic-border-light);
  border-bottom: none;
  width: 200px;
  min-height: unset;
}

.aura-tabs--vertical .aura-tabs__indicator {
  width: 2px;
  height: 48px;
  right: 0;
  bottom: auto;
  transform: translateY(calc(var(--active-index) * 100%));
}

/* Size variants */
.aura-tabs--small .aura-tabs__tab {
  padding: var(--spacing-component-padding-sm) var(--spacing-component-padding-md);
  font-size: var(--typography-fontSize-sm);
  min-height: 36px;
}

.aura-tabs--small .aura-tabs__icon {
  width: 16px;
  height: 16px;
}

.aura-tabs--large .aura-tabs__tab {
  padding: var(--spacing-component-padding-lg) var(--spacing-component-padding-xl);
  font-size: var(--typography-fontSize-lg);
  min-height: 56px;
}

.aura-tabs--large .aura-tabs__icon {
  width: 24px;
  height: 24px;
}

/* Tab panel */
.aura-tabs__panel {
  padding: var(--spacing-component-padding-lg);
  outline: none;
  animation: fadeIn var(--animations-duration-fast) var(--animations-easing-easeOut);
}

.aura-tabs__panel:focus-visible {
  box-shadow: inset var(--shadows-focus-primary);
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

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .aura-tabs__tab,
  .aura-tabs__indicator,
  .aura-tabs__panel {
    transition: none;
    animation: none;
  }
}

/* Mobile responsive */
@media (max-width: 640px) {
  .aura-tabs__list {
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: thin;
    -webkit-overflow-scrolling: touch;
  }
  
  .aura-tabs__tab {
    flex-shrink: 0;
  }
}
`;