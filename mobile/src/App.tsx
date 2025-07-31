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

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
    },
  },
});

const App: React.FC = () => {
  useEffect(() => {
    // Hide splash screen after app loads
    SplashScreen.hide();
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