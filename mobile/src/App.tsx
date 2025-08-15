import React, { useEffect } from 'react';
import { StatusBar } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { NavigationContainer } from '@react-navigation/native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Provider as PaperProvider } from 'react-native-paper';
import Toast from 'react-native-toast-message';
import SplashScreen from 'react-native-splash-screen';
import { NetworkProvider } from 'react-native-offline';

import { AppNavigator } from '@navigation/AppNavigator';
import { AuthProvider } from '@contexts/AuthContext';
import { theme } from '@constants/theme';
import { toastConfig } from '@constants/toastConfig';
import { syncManager } from '@sync';
import { OfflineIndicator } from '@components/sync';
import { CACHE_CONFIG } from '@constants/config';
import { notificationService } from '@services/notifications';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: CACHE_CONFIG.DEFAULT_STALE_TIME,
      cacheTime: CACHE_CONFIG.DEFAULT_CACHE_TIME,
    },
  },
});

const App: React.FC = () => {
  useEffect(() => {
    // Hide splash screen after app loads
    SplashScreen.hide();

    // Initialize sync manager
    syncManager.initialize().catch(error => {
      console.error('Failed to initialize sync manager:', error);
    });

    // Initialize notification service
    notificationService.initialize().catch(error => {
      console.error('Failed to initialize notification service:', error);
    });

    return () => {
      // Cleanup on app unmount
      syncManager.destroy();
    };
  }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <NetworkProvider>
            <AuthProvider>
              <PaperProvider theme={theme}>
                <NavigationContainer>
                  <StatusBar
                    barStyle="dark-content"
                    backgroundColor="transparent"
                    translucent
                  />
                  <OfflineIndicator />
                  <AppNavigator />
                  <Toast config={toastConfig} />
                </NavigationContainer>
              </PaperProvider>
            </AuthProvider>
          </NetworkProvider>
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
};

export default App;
