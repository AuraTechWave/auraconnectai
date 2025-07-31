import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { BaseToast, ErrorToast, InfoToast } from 'react-native-toast-message';

const toastStyles = {
  success: {
    borderLeftColor: '#10b981',
    icon: 'check-circle',
    iconColor: '#10b981',
  },
  error: {
    borderLeftColor: '#ef4444',
    icon: 'alert-circle',
    iconColor: '#ef4444',
  },
  info: {
    borderLeftColor: '#3b82f6',
    icon: 'information',
    iconColor: '#3b82f6',
  },
  warning: {
    borderLeftColor: '#f59e0b',
    icon: 'alert',
    iconColor: '#f59e0b',
  },
};

const CustomToast = ({ type, text1, text2 }: any) => {
  const style = toastStyles[type as keyof typeof toastStyles];

  return (
    <View style={[styles.container, { borderLeftColor: style.borderLeftColor }]}>
      <Icon name={style.icon} size={24} color={style.iconColor} />
      <View style={styles.textContainer}>
        <Text style={styles.title}>{text1}</Text>
        {text2 && <Text style={styles.message}>{text2}</Text>}
      </View>
    </View>
  );
};

export const toastConfig = {
  success: (props: any) => <CustomToast type="success" {...props} />,
  error: (props: any) => <CustomToast type="error" {...props} />,
  info: (props: any) => <CustomToast type="info" {...props} />,
  warning: (props: any) => <CustomToast type="warning" {...props} />,
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 8,
    borderLeftWidth: 4,
    marginHorizontal: 16,
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    minHeight: 60,
  },
  textContainer: {
    flex: 1,
    marginLeft: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1f2937',
  },
  message: {
    fontSize: 14,
    color: '#6b7280',
    marginTop: 2,
  },
});