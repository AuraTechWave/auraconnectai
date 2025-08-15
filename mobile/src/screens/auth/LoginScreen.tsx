import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import {
  TextInput,
  Button,
  Text,
  useTheme,
  ActivityIndicator,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { useForm, Controller } from 'react-hook-form';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

import { useAuth } from '@hooks/useAuth';
import { Logo } from '@components/common/Logo';
import { showToast } from '@utils/toast';

interface LoginFormData {
  username: string;
  password: string;
}

export const LoginScreen: React.FC = () => {
  const theme = useTheme();
  const navigation = useNavigation();
  const { login } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    defaultValues: {
      username: '',
      password: '',
    },
  });

  const onSubmit = async (data: LoginFormData) => {
    setIsLoading(true);
    try {
      await login(data.username, data.password);
      showToast('success', 'Welcome back!', 'Successfully logged in');
    } catch (error: any) {
      showToast(
        'error',
        'Login Failed',
        error.message || 'Invalid credentials',
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}>
          <View style={styles.logoContainer}>
            <Logo size={120} />
            <Text variant="headlineMedium" style={styles.title}>
              Welcome to AuraConnect
            </Text>
            <Text variant="bodyLarge" style={styles.subtitle}>
              Restaurant Management System
            </Text>
          </View>

          <View style={styles.formContainer}>
            <Controller
              control={control}
              name="username"
              rules={{
                required: 'Username is required',
                minLength: {
                  value: 3,
                  message: 'Username must be at least 3 characters',
                },
              }}
              render={({ field: { onChange, onBlur, value } }) => (
                <TextInput
                  label="Username"
                  value={value}
                  onChangeText={onChange}
                  onBlur={onBlur}
                  mode="outlined"
                  autoCapitalize="none"
                  autoCorrect={false}
                  error={!!errors.username}
                  left={<TextInput.Icon icon="account" />}
                  style={styles.input}
                />
              )}
            />
            {errors.username && (
              <Text style={styles.errorText}>{errors.username.message}</Text>
            )}

            <Controller
              control={control}
              name="password"
              rules={{
                required: 'Password is required',
                minLength: {
                  value: 6,
                  message: 'Password must be at least 6 characters',
                },
              }}
              render={({ field: { onChange, onBlur, value } }) => (
                <TextInput
                  label="Password"
                  value={value}
                  onChangeText={onChange}
                  onBlur={onBlur}
                  mode="outlined"
                  secureTextEntry={!showPassword}
                  error={!!errors.password}
                  left={<TextInput.Icon icon="lock" />}
                  right={
                    <TextInput.Icon
                      icon={showPassword ? 'eye-off' : 'eye'}
                      onPress={() => setShowPassword(!showPassword)}
                    />
                  }
                  style={styles.input}
                />
              )}
            />
            {errors.password && (
              <Text style={styles.errorText}>{errors.password.message}</Text>
            )}

            <Button
              mode="text"
              onPress={() => navigation.navigate('ForgotPassword' as never)}
              style={styles.forgotButton}>
              Forgot Password?
            </Button>

            <Button
              mode="contained"
              onPress={handleSubmit(onSubmit)}
              loading={isLoading}
              disabled={isLoading}
              style={styles.loginButton}
              contentStyle={styles.loginButtonContent}>
              {isLoading ? 'Logging in...' : 'Login'}
            </Button>
          </View>

          <View style={styles.demoContainer}>
            <Text variant="bodySmall" style={styles.demoText}>
              Demo Credentials:
            </Text>
            <Text variant="bodySmall" style={styles.demoCredentials}>
              Admin: admin / secret
            </Text>
            <Text variant="bodySmall" style={styles.demoCredentials}>
              Manager: manager / secret
            </Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingVertical: 32,
  },
  logoContainer: {
    alignItems: 'center',
    marginBottom: 48,
  },
  title: {
    marginTop: 16,
    fontWeight: 'bold',
  },
  subtitle: {
    marginTop: 8,
    opacity: 0.7,
  },
  formContainer: {
    marginBottom: 32,
  },
  input: {
    marginBottom: 16,
  },
  errorText: {
    color: '#B00020',
    fontSize: 12,
    marginTop: -12,
    marginBottom: 12,
    marginLeft: 12,
  },
  forgotButton: {
    alignSelf: 'flex-end',
    marginBottom: 24,
  },
  loginButton: {
    marginTop: 8,
  },
  loginButtonContent: {
    paddingVertical: 8,
  },
  demoContainer: {
    alignItems: 'center',
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
  },
  demoText: {
    opacity: 0.7,
    marginBottom: 8,
  },
  demoCredentials: {
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    marginBottom: 4,
  },
});
