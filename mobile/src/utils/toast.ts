import Toast from 'react-native-toast-message';

type ToastType = 'success' | 'error' | 'info' | 'warning';

export const showToast = (
  type: ToastType,
  title: string,
  message?: string,
  duration?: number,
) => {
  Toast.show({
    type,
    text1: title,
    text2: message,
    position: 'top',
    visibilityTime: duration || 3000,
    autoHide: true,
    topOffset: 50,
  });
};