import React, { lazy, Suspense } from 'react';
import {
  View,
  StyleSheet,
  Modal,
  ActivityIndicator,
  Dimensions,
} from 'react-native';
import { Text, useTheme } from 'react-native-paper';

// Lazy load Lottie to reduce initial bundle size
const LottieView = lazy(() => import('lottie-react-native'));

interface LoadingOverlayProps {
  visible: boolean;
  message?: string;
  type?: 'spinner' | 'lottie';
  lottieSource?: any;
}

const { width, height } = Dimensions.get('window');

export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({
  visible,
  message = 'Loading...',
  type = 'spinner',
  lottieSource,
}) => {
  const theme = useTheme();

  return (
    <Modal
      transparent
      animationType="fade"
      visible={visible}
      statusBarTranslucent>
      <View style={styles.container}>
        <View
          style={[styles.content, { backgroundColor: theme.colors.surface }]}>
          {type === 'spinner' ? (
            <ActivityIndicator
              size="large"
              color={theme.colors.primary}
              style={styles.spinner}
            />
          ) : (
            <Suspense
              fallback={
                <ActivityIndicator
                  size="large"
                  color={theme.colors.primary}
                  style={styles.spinner}
                />
              }>
              <LottieView
                source={
                  lottieSource || require('@assets/animations/loading.json')
                }
                autoPlay
                loop
                style={styles.lottie}
              />
            </Suspense>
          )}
          <Text variant="bodyLarge" style={styles.message}>
            {message}
          </Text>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  content: {
    borderRadius: 12,
    padding: 24,
    alignItems: 'center',
    minWidth: width * 0.6,
    maxWidth: width * 0.8,
    elevation: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  spinner: {
    marginBottom: 16,
  },
  lottie: {
    width: 100,
    height: 100,
    marginBottom: 16,
  },
  message: {
    textAlign: 'center',
  },
});
