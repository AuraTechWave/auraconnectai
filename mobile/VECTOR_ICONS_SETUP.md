# React Native Vector Icons Setup Guide

This guide ensures `react-native-vector-icons` is properly configured for both iOS and Android.

## Installation

```bash
npm install react-native-vector-icons
# or
yarn add react-native-vector-icons
```

## iOS Setup

### 1. Add Font Files to iOS Project

```bash
cd ios && pod install
```

### 2. Update Info.plist

Add the following to `ios/AuraConnect/Info.plist`:

```xml
<key>UIAppFonts</key>
<array>
  <string>AntDesign.ttf</string>
  <string>Entypo.ttf</string>
  <string>EvilIcons.ttf</string>
  <string>Feather.ttf</string>
  <string>FontAwesome.ttf</string>
  <string>Foundation.ttf</string>
  <string>Ionicons.ttf</string>
  <string>MaterialIcons.ttf</string>
  <string>MaterialCommunityIcons.ttf</string>
  <string>SimpleLineIcons.ttf</string>
  <string>Octicons.ttf</string>
  <string>Zocial.ttf</string>
</array>
```

### 3. Clean and Rebuild

```bash
cd ios
rm -rf build/
cd ..
npx react-native run-ios
```

## Android Setup

### 1. Update android/app/build.gradle

Add the following to `android/app/build.gradle`:

```gradle
apply from: file("../../node_modules/react-native-vector-icons/fonts.gradle")
```

### 2. For React Native 0.60+

The package should auto-link. If not, add to `android/settings.gradle`:

```gradle
include ':react-native-vector-icons'
project(':react-native-vector-icons').projectDir = new File(rootProject.projectDir, '../node_modules/react-native-vector-icons/android')
```

And to `android/app/build.gradle` dependencies:

```gradle
implementation project(':react-native-vector-icons')
```

### 3. Clean and Rebuild

```bash
cd android
./gradlew clean
cd ..
npx react-native run-android
```

## Troubleshooting

### Icons Not Showing on iOS

1. Make sure the font files are added to the Xcode project
2. Clean the build folder: `rm -rf ios/build/`
3. Reset Metro cache: `npx react-native start --reset-cache`

### Icons Not Showing on Android

1. Ensure the gradle configuration is correct
2. Clean gradle: `cd android && ./gradlew clean`
3. Rebuild: `npx react-native run-android`

### TypeScript Issues

If you see TypeScript errors, install types:

```bash
npm install --save-dev @types/react-native-vector-icons
```

## Usage in Code

```typescript
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';

// In component
<MaterialCommunityIcons name="home" size={24} color="#000" />
```

## Reducing Bundle Size

To include only specific fonts, update the gradle configuration:

```gradle
project.ext.vectoricons = [
    iconFontNames: [ 'MaterialCommunityIcons.ttf', 'MaterialIcons.ttf' ]
]

apply from: file("../../node_modules/react-native-vector-icons/fonts.gradle")
```