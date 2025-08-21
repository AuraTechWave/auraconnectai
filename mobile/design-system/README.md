# AuraConnect Design System

This design system uses [Style Dictionary](https://amzn.github.io/style-dictionary/) to generate design tokens for multiple platforms from a single source of truth.

## Structure

```
design-system/
├── tokens/               # Source design tokens
│   ├── colors.json      # Color palette
│   ├── spacing.json     # Spacing and sizing
│   ├── typography.json  # Font properties
│   ├── shadows.json     # Shadow definitions
│   └── animation.json   # Animation timings
├── config.js            # Style Dictionary configuration
├── build.js             # Build script
└── build/               # Generated output
    ├── ts/              # TypeScript definitions
    ├── ios/             # iOS resources
    ├── android/         # Android resources
    └── docs/            # Documentation
```

## Usage

### Install dependencies
```bash
cd design-system
npm install
```

### Build tokens
```bash
npm run build
```

### Watch for changes
```bash
npm run watch
```

### Clean build artifacts
```bash
npm run clean
```

## Generated Files

### React Native
- `../src/constants/generated/tokens.js` - JavaScript module with all tokens

### TypeScript
- `build/ts/index.d.ts` - Type definitions for tokens

### iOS
- `build/ios/DesignTokens.h` - Objective-C header
- `build/ios/DesignTokens.m` - Objective-C implementation

### Android
- `build/android/design_tokens_colors.xml` - Color resources
- `build/android/design_tokens_dimens.xml` - Dimension resources

### Documentation
- `build/docs/tokens.md` - Markdown table of all tokens

## Adding New Tokens

1. Add your tokens to the appropriate JSON file in the `tokens/` directory
2. Run `npm run build` to generate the platform-specific files
3. Import the generated tokens in your React Native components:

```javascript
import { tokens } from '../constants/generated/tokens';

const styles = StyleSheet.create({
  container: {
    backgroundColor: tokens.colorBackgroundPrimary,
    padding: tokens.spacingMd,
  },
});
```

## Custom Transforms

The configuration includes custom transforms for:
- `size/dp` - Converts size values to Android dp units
- `time/ms` - Converts time values to milliseconds

## Custom Formats

- `javascript/module-flat` - Generates a flat JavaScript object for React Native

## Integration with CI/CD

Add this to your CI/CD pipeline to ensure tokens are always up to date:

```yaml
- name: Build Design Tokens
  run: |
    cd mobile/design-system
    npm ci
    npm run build
```

## Best Practices

1. **Semantic Naming**: Use semantic names like `colorTextPrimary` instead of `colorGray900`
2. **Token References**: Use references to maintain consistency: `{ "value": "{color.neutral.900.value}" }`
3. **Platform Specifics**: Use transforms to handle platform-specific requirements
4. **Version Control**: Commit both source tokens and generated files for easier debugging