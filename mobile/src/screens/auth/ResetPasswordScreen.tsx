import React, { useState } from 'react';
import { View, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import { TextInput, Button, Text, useTheme } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { useForm, Controller } from 'react-hook-form';

import { authService } from '@services/auth.service';
import { showToast } from '@utils/toast';
import { AuthStackParamList } from '@navigation/AuthNavigator';

interface ResetPasswordFormData {
  password: string;
  confirmPassword: string;
}

type ResetPasswordRouteProp = RouteProp<AuthStackParamList, 'ResetPassword'>;

export const ResetPasswordScreen: React.FC = () => {
  const theme = useTheme();
  const navigation = useNavigation();
  const route = useRoute<ResetPasswordRouteProp>();
  const { token } = route.params;

  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ResetPasswordFormData>({
    defaultValues: {
      password: '',
      confirmPassword: '',
    },
  });

  const password = watch('password');

  const onSubmit = async (data: ResetPasswordFormData) => {
    setIsLoading(true);
    try {
      await authService.resetPassword(token, data.password);
      showToast(
        'success',
        'Password Reset',
        'Your password has been successfully reset',
      );
      navigation.navigate('Login' as never);
    } catch (error: any) {
      showToast(
        'error',
        'Reset Failed',
        error.message || 'Unable to reset password',
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
        <View style={styles.content}>
          <Text variant="headlineMedium" style={styles.title}>
            Reset Password
          </Text>
          <Text variant="bodyLarge" style={styles.description}>
            Enter your new password below.
          </Text>

          <Controller
            control={control}
            name="password"
            rules={{
              required: 'Password is required',
              minLength: {
                value: 8,
                message: 'Password must be at least 8 characters',
              },
              pattern: {
                value:
                  /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/,
                message:
                  'Password must contain uppercase, lowercase, number and special character',
              },
            }}
            render={({ field: { onChange, onBlur, value } }) => (
              <TextInput
                label="New Password"
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

          <Controller
            control={control}
            name="confirmPassword"
            rules={{
              required: 'Please confirm your password',
              validate: value => value === password || 'Passwords do not match',
            }}
            render={({ field: { onChange, onBlur, value } }) => (
              <TextInput
                label="Confirm Password"
                value={value}
                onChangeText={onChange}
                onBlur={onBlur}
                mode="outlined"
                secureTextEntry={!showConfirmPassword}
                error={!!errors.confirmPassword}
                left={<TextInput.Icon icon="lock-check" />}
                right={
                  <TextInput.Icon
                    icon={showConfirmPassword ? 'eye-off' : 'eye'}
                    onPress={() => setShowConfirmPassword(!showConfirmPassword)}
                  />
                }
                style={styles.input}
              />
            )}
          />
          {errors.confirmPassword && (
            <Text style={styles.errorText}>
              {errors.confirmPassword.message}
            </Text>
          )}

          <Button
            mode="contained"
            onPress={handleSubmit(onSubmit)}
            loading={isLoading}
            disabled={isLoading}
            style={styles.button}
            contentStyle={styles.buttonContent}>
            {isLoading ? 'Resetting...' : 'Reset Password'}
          </Button>

          <Button
            mode="text"
            onPress={() => navigation.navigate('Login' as never)}
            style={styles.backButton}>
            Back to Login
          </Button>
        </View>
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
  content: {
    flex: 1,
    paddingHorizontal: 24,
    paddingVertical: 32,
    justifyContent: 'center',
  },
  title: {
    fontWeight: 'bold',
    marginBottom: 16,
  },
  description: {
    opacity: 0.7,
    marginBottom: 32,
    lineHeight: 24,
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
  button: {
    marginTop: 8,
  },
  buttonContent: {
    paddingVertical: 8,
  },
  backButton: {
    marginTop: 16,
  },
});
