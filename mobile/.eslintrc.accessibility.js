// Custom accessibility rules for React Native
module.exports = {
  rules: {
    // Enforce accessibility properties on touchable components
    'react-native-a11y/has-accessibility-props': {
      create(context) {
        return {
          JSXOpeningElement(node) {
            const elementName = node.name.name;
            const touchableComponents = [
              'TouchableOpacity',
              'TouchableHighlight',
              'TouchableWithoutFeedback',
              'TouchableNativeFeedback',
              'Pressable',
              'Button',
            ];

            if (touchableComponents.includes(elementName)) {
              const hasAccessibilityLabel = node.attributes.some(
                (attr) => attr.name && attr.name.name === 'accessibilityLabel'
              );
              const hasAccessibilityHint = node.attributes.some(
                (attr) => attr.name && attr.name.name === 'accessibilityHint'
              );
              const hasAccessibilityRole = node.attributes.some(
                (attr) => attr.name && attr.name.name === 'accessibilityRole'
              );

              if (!hasAccessibilityLabel) {
                context.report({
                  node,
                  message: `${elementName} should have an accessibilityLabel prop for screen readers`,
                });
              }

              if (!hasAccessibilityRole) {
                context.report({
                  node,
                  message: `${elementName} should have an accessibilityRole prop`,
                });
              }
            }
          },
        };
      },
    },

    // Enforce minimum touch target size (44x44 points)
    'react-native-a11y/touchable-has-min-size': {
      create(context) {
        return {
          JSXOpeningElement(node) {
            const elementName = node.name.name;
            const touchableComponents = [
              'TouchableOpacity',
              'TouchableHighlight',
              'TouchableWithoutFeedback',
              'TouchableNativeFeedback',
              'Pressable',
            ];

            if (touchableComponents.includes(elementName)) {
              const styleAttr = node.attributes.find(
                (attr) => attr.name && attr.name.name === 'style'
              );
              
              if (styleAttr && styleAttr.value) {
                // This is a simplified check - in practice, you'd need to analyze the style object
                context.report({
                  node,
                  message: `Ensure ${elementName} has a minimum touch target size of 44x44 points`,
                  suggest: [
                    {
                      desc: 'Add minimum height and width',
                      fix(fixer) {
                        return fixer.insertTextAfter(
                          node.name,
                          ' style={{ minHeight: 44, minWidth: 44, ...style }}'
                        );
                      },
                    },
                  ],
                });
              }
            }
          },
        };
      },
    },

    // Enforce accessibility properties on Image components
    'react-native-a11y/image-has-accessible-text': {
      create(context) {
        return {
          JSXOpeningElement(node) {
            if (node.name.name === 'Image') {
              const hasAccessibilityLabel = node.attributes.some(
                (attr) => attr.name && attr.name.name === 'accessibilityLabel'
              );
              const isAccessibilityIgnored = node.attributes.some(
                (attr) => 
                  attr.name && 
                  attr.name.name === 'accessibilityElementsHidden' &&
                  attr.value.expression.value === true
              );

              if (!hasAccessibilityLabel && !isAccessibilityIgnored) {
                context.report({
                  node,
                  message: 'Image components should have an accessibilityLabel or be marked as decorative',
                });
              }
            }
          },
        };
      },
    },

    // Ensure TextInput has proper labels
    'react-native-a11y/textinput-has-accessible-label': {
      create(context) {
        return {
          JSXOpeningElement(node) {
            if (node.name.name === 'TextInput') {
              const hasAccessibilityLabel = node.attributes.some(
                (attr) => attr.name && attr.name.name === 'accessibilityLabel'
              );
              const hasPlaceholder = node.attributes.some(
                (attr) => attr.name && attr.name.name === 'placeholder'
              );

              if (!hasAccessibilityLabel && !hasPlaceholder) {
                context.report({
                  node,
                  message: 'TextInput should have an accessibilityLabel or placeholder for screen readers',
                });
              }
            }
          },
        };
      },
    },

    // Enforce proper color contrast
    'react-native-a11y/text-has-accessible-color': {
      create(context) {
        return {
          JSXOpeningElement(node) {
            if (node.name.name === 'Text') {
              // This is a placeholder - actual implementation would need to
              // analyze color values and check WCAG contrast ratios
              const styleAttr = node.attributes.find(
                (attr) => attr.name && attr.name.name === 'style'
              );
              
              if (styleAttr) {
                // Add warning comment
                context.report({
                  node,
                  message: 'Ensure text color has sufficient contrast ratio (4.5:1 for normal text, 3:1 for large text)',
                  severity: 'warning',
                });
              }
            }
          },
        };
      },
    },
  },
};

// Accessibility checklist for React Native components:
// 1. All interactive elements must have accessibilityLabel
// 2. Use accessibilityRole to convey element purpose
// 3. Use accessibilityHint for complex interactions
// 4. Ensure minimum touch target size of 44x44 points
// 5. Group related elements with accessible={true} on parent View
// 6. Use accessibilityLiveRegion for dynamic content updates
// 7. Test with VoiceOver (iOS) and TalkBack (Android)
// 8. Use accessibilityState for dynamic states (checked, selected, disabled)
// 9. Implement proper focus management with accessibilityViewIsModal
// 10. Use importantForAccessibility to control screen reader focus