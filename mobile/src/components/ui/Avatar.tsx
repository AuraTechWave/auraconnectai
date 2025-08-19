import React from 'react';
import {
  View,
  Text,
  Image,
  StyleSheet,
  ViewStyle,
  TextStyle,
  TouchableOpacity,
} from 'react-native';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors, spacing, typography, borderRadius } from '../../constants/designSystem';

interface AvatarProps {
  source?: { uri: string } | number;
  name?: string;
  size?: 'small' | 'medium' | 'large' | 'xlarge';
  variant?: 'circle' | 'rounded' | 'square';
  backgroundColor?: string;
  textColor?: string;
  icon?: string;
  status?: 'online' | 'offline' | 'busy' | 'away';
  onPress?: () => void;
  style?: ViewStyle;
}

export const Avatar: React.FC<AvatarProps> = ({
  source,
  name,
  size = 'medium',
  variant = 'circle',
  backgroundColor,
  textColor,
  icon,
  status,
  onPress,
  style,
}) => {
  const getSize = (): number => {
    const sizes: Record<string, number> = {
      small: 32,
      medium: 40,
      large: 56,
      xlarge: 80,
    };
    return sizes[size];
  };

  const getAvatarStyle = (): ViewStyle => {
    const avatarSize = getSize();
    const borderRadiusValue = variant === 'circle' 
      ? avatarSize / 2 
      : variant === 'rounded' 
      ? borderRadius.md 
      : 0;

    return {
      width: avatarSize,
      height: avatarSize,
      borderRadius: borderRadiusValue,
      backgroundColor: backgroundColor || getColorFromString(name || ''),
      alignItems: 'center',
      justifyContent: 'center',
      overflow: 'hidden',
    };
  };

  const getTextStyle = (): TextStyle => {
    const textSizes: Record<string, number> = {
      small: typography.fontSize.body,
      medium: typography.fontSize.bodyLarge,
      large: typography.fontSize.title,
      xlarge: typography.fontSize.h2,
    };

    return {
      fontSize: textSizes[size],
      fontWeight: typography.fontWeight.semiBold,
      color: textColor || colors.text.inverse,
    };
  };

  const getIconSize = (): number => {
    const sizes: Record<string, number> = {
      small: 16,
      medium: 20,
      large: 28,
      xlarge: 40,
    };
    return sizes[size];
  };

  const getInitials = (fullName: string): string => {
    const names = fullName.trim().split(' ');
    if (names.length === 1) {
      return names[0].substring(0, 2).toUpperCase();
    }
    return (names[0][0] + names[names.length - 1][0]).toUpperCase();
  };

  const getColorFromString = (str: string): string => {
    const colorPalette = [
      colors.primary[500],
      colors.secondary[500],
      colors.accent[500],
      colors.success[500],
      colors.warning[500],
      '#9333ea',
      '#06b6d4',
      '#ec4899',
    ];
    
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colorPalette[Math.abs(hash) % colorPalette.length];
  };

  const getStatusStyle = (): ViewStyle => {
    const statusSize = getSize() * 0.3;
    const statusColors: Record<string, string> = {
      online: colors.success[500],
      offline: colors.neutral[400],
      busy: colors.error[500],
      away: colors.warning[500],
    };

    return {
      position: 'absolute',
      bottom: 0,
      right: 0,
      width: statusSize,
      height: statusSize,
      borderRadius: statusSize / 2,
      backgroundColor: status ? statusColors[status] : 'transparent',
      borderWidth: 2,
      borderColor: colors.background.primary,
    };
  };

  const renderContent = () => {
    if (source) {
      return (
        <Image
          source={source}
          style={{ width: '100%', height: '100%' }}
          resizeMode="cover"
        />
      );
    }

    if (icon) {
      return (
        <MaterialCommunityIcons
          name={icon}
          size={getIconSize()}
          color={textColor || colors.text.inverse}
        />
      );
    }

    if (name) {
      return <Text style={getTextStyle()}>{getInitials(name)}</Text>;
    }

    return (
      <MaterialCommunityIcons
        name="account"
        size={getIconSize()}
        color={textColor || colors.text.inverse}
      />
    );
  };

  const avatarContent = (
    <View style={[getAvatarStyle(), style]}>
      {renderContent()}
      {status && <View style={getStatusStyle()} />}
    </View>
  );

  if (onPress) {
    return (
      <TouchableOpacity onPress={onPress} activeOpacity={0.7}>
        {avatarContent}
      </TouchableOpacity>
    );
  }

  return avatarContent;
};

interface AvatarGroupProps {
  avatars: Array<{
    source?: { uri: string } | number;
    name?: string;
    icon?: string;
  }>;
  max?: number;
  size?: 'small' | 'medium' | 'large' | 'xlarge';
  spacing?: number;
}

export const AvatarGroup: React.FC<AvatarGroupProps> = ({
  avatars,
  max = 4,
  size = 'medium',
  spacing = -8,
}) => {
  const displayAvatars = avatars.slice(0, max);
  const remainingCount = avatars.length - max;

  return (
    <View style={styles.groupContainer}>
      {displayAvatars.map((avatar, index) => (
        <View
          key={index}
          style={[
            styles.groupAvatar,
            {
              marginLeft: index === 0 ? 0 : spacing,
              zIndex: displayAvatars.length - index,
            },
          ]}
        >
          <Avatar {...avatar} size={size} />
        </View>
      ))}
      {remainingCount > 0 && (
        <View
          style={[
            styles.groupAvatar,
            {
              marginLeft: spacing,
              zIndex: 0,
            },
          ]}
        >
          <Avatar
            name={`+${remainingCount}`}
            size={size}
            backgroundColor={colors.neutral[300]}
            textColor={colors.text.primary}
          />
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  groupContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  groupAvatar: {
    borderWidth: 2,
    borderColor: colors.background.primary,
    borderRadius: borderRadius.full,
  },
});