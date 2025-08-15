import React from 'react';
import { View, StyleSheet } from 'react-native';
import { ActivityIndicator, Text, useTheme } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Logo } from '@components/common/Logo';

export const LoadingScreen: React.FC = () => {
  const theme = useTheme();

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        <Logo size={100} />
        <ActivityIndicator
          size="large"
          color={theme.colors.primary}
          style={styles.spinner}
        />
        <Text variant="bodyLarge" style={styles.text}>
          Loading...
        </Text>
      </View>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  spinner: {
    marginTop: 32,
  },
  text: {
    marginTop: 16,
    opacity: 0.7,
  },
});
