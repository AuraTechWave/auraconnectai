import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Text, useTheme } from 'react-native-paper';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

interface LogoProps {
  size?: number;
  showText?: boolean;
}

export const Logo: React.FC<LogoProps> = ({ size = 80, showText = false }) => {
  const theme = useTheme();

  return (
    <View style={styles.container}>
      <View
        style={[
          styles.logoContainer,
          {
            width: size,
            height: size,
            backgroundColor: theme.colors.primary,
          },
        ]}>
        <Icon name="chef-hat" size={size * 0.6} color="#fff" />
      </View>
      {showText && (
        <Text variant="headlineSmall" style={styles.text}>
          AuraConnect
        </Text>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  logoContainer: {
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
  },
  text: {
    marginTop: 12,
    fontWeight: 'bold',
  },
});