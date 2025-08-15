import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import NetInfo from '@react-native-community/netinfo';
import { colors, typography } from '@theme';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

export const OfflineIndicator: React.FC = () => {
  const [isOnline, setIsOnline] = useState(true);
  const slideAnim = new Animated.Value(-60);

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener(state => {
      const online = state.isConnected ?? false;
      setIsOnline(online);

      Animated.timing(slideAnim, {
        toValue: online ? -60 : 0,
        duration: 300,
        useNativeDriver: true,
      }).start();
    });

    return unsubscribe;
  }, []);

  return (
    <Animated.View
      style={[
        styles.container,
        {
          transform: [{ translateY: slideAnim }],
        },
      ]}>
      <View style={styles.content}>
        <Icon
          name={isOnline ? 'wifi' : 'wifi-off'}
          size={20}
          color={colors.white}
          style={styles.icon}
        />
        <Text style={styles.text}>
          {isOnline ? 'Back Online' : 'Offline Mode'}
        </Text>
      </View>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    backgroundColor: colors.warning,
    paddingTop: 40, // Account for status bar
    paddingBottom: 10,
    zIndex: 1000,
    elevation: 10,
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  icon: {
    marginRight: 8,
  },
  text: {
    ...typography.body,
    color: colors.white,
    fontWeight: '600',
  },
});
