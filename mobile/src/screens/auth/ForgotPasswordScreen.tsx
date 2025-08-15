import React, { useState } from 'react';
import { View, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import { TextInput, Button, Text, useTheme } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { useForm, Controller } from 'react-hook-form';

import { authService } from '@services/auth.service';
import { showToast } from '@utils/toast';

interface ForgotPasswordFormData {
  email: string;
}

export const ForgotPasswordScreen: React.FC = () => {
  const theme = useTheme();
  const navigation = useNavigation();
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormData>({
    defaultValues: {
      email: '',
    },
  });

  const onSubmit = async (data: ForgotPasswordFormData) => {
    setIsLoading(true);
    try {
      await authService.forgotPassword(data.email);
      setIsSubmitted(true);
      showToast(
        'success',
        'Email Sent',
        'Check your email for reset instructions',
      );
    } catch (error: any) {
      showToast(
        'error',
        'Request Failed',
        error.message || 'Unable to process request',
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (isSubmitted) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.content}>
          <Text variant="headlineMedium" style={styles.title}>
            Check Your Email
          </Text>
          <Text variant="bodyLarge" style={styles.description}>
            We've sent password reset instructions to your email address.
          </Text>
          <Button
            mode="contained"
            onPress={() => navigation.goBack()}
            style={styles.button}>
            Back to Login
          </Button>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}>
        <View style={styles.content}>
          <Text variant="headlineMedium" style={styles.title}>
            Forgot Password?
          </Text>
          <Text variant="bodyLarge" style={styles.description}>
            Enter your email address and we'll send you instructions to reset
            your password.
          </Text>

          <Controller
            control={control}
            name="email"
            rules={{
              required: 'Email is required',
              pattern: {
                value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                message: 'Invalid email address',
              },
            }}
            render={({ field: { onChange, onBlur, value } }) => (
              <TextInput
                label="Email Address"
                value={value}
                onChangeText={onChange}
                onBlur={onBlur}
                mode="outlined"
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                error={!!errors.email}
                left={<TextInput.Icon icon="email" />}
                style={styles.input}
              />
            )}
          />
          {errors.email && (
            <Text style={styles.errorText}>{errors.email.message}</Text>
          )}

          <Button
            mode="contained"
            onPress={handleSubmit(onSubmit)}
            loading={isLoading}
            disabled={isLoading}
            style={styles.button}
            contentStyle={styles.buttonContent}>
            {isLoading ? 'Sending...' : 'Send Reset Instructions'}
          </Button>

          <Button
            mode="text"
            onPress={() => navigation.goBack()}
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
