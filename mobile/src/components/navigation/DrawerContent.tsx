import React from 'react';
import { View, StyleSheet } from 'react-native';
import {
  DrawerContentScrollView,
  DrawerContentComponentProps,
} from '@react-navigation/drawer';
import {
  Avatar,
  Title,
  Caption,
  Drawer,
  Text,
  TouchableRipple,
  Switch,
  useTheme,
  Divider,
} from 'react-native-paper';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

import { useAuth } from '@hooks/useAuth';
import { useAppStore } from '@store/app.store';

export const DrawerContent: React.FC<DrawerContentComponentProps> = props => {
  const theme = useTheme();
  const { user, logout } = useAuth();
  const { notifications, setNotifications } = useAppStore();

  const handleLogout = async () => {
    await logout();
  };

  return (
    <View style={styles.container}>
      <DrawerContentScrollView {...props}>
        <View style={styles.drawerContent}>
          <View style={styles.userInfoSection}>
            <View style={styles.userInfo}>
              <Avatar.Icon
                icon="account"
                size={50}
                style={{ backgroundColor: theme.colors.primary }}
              />
              <View style={styles.userDetails}>
                <Title style={styles.title}>{user?.full_name || 'User'}</Title>
                <Caption style={styles.caption}>{user?.email}</Caption>
              </View>
            </View>
          </View>

          <Drawer.Section style={styles.drawerSection}>
            <DrawerItem
              icon="view-dashboard"
              label="Dashboard"
              onPress={() => props.navigation.navigate('Dashboard')}
            />
            <DrawerItem
              icon="receipt"
              label="Orders"
              onPress={() => props.navigation.navigate('Orders')}
            />
            <DrawerItem
              icon="account-group"
              label="Staff"
              onPress={() => props.navigation.navigate('Staff')}
            />
            <DrawerItem
              icon="food-variant"
              label="Menu"
              onPress={() => props.navigation.navigate('Menu')}
            />
            <DrawerItem
              icon="chart-line"
              label="Analytics"
              onPress={() => props.navigation.navigate('Analytics')}
            />
          </Drawer.Section>

          <Drawer.Section title="Preferences">
            <TouchableRipple onPress={() => setNotifications(!notifications)}>
              <View style={styles.preference}>
                <Text>Notifications</Text>
                <View pointerEvents="none">
                  <Switch value={notifications} />
                </View>
              </View>
            </TouchableRipple>
          </Drawer.Section>

          <Drawer.Section>
            <DrawerItem
              icon="cog"
              label="Settings"
              onPress={() => props.navigation.navigate('Settings' as never)}
            />
            <DrawerItem
              icon="help-circle"
              label="Help & Support"
              onPress={() => props.navigation.navigate('Help' as never)}
            />
          </Drawer.Section>
        </View>
      </DrawerContentScrollView>

      <Drawer.Section style={styles.bottomDrawerSection}>
        <DrawerItem icon="logout" label="Sign Out" onPress={handleLogout} />
      </Drawer.Section>
    </View>
  );
};

const DrawerItem: React.FC<{
  icon: string;
  label: string;
  onPress: () => void;
}> = ({ icon, label, onPress }) => (
  <Drawer.Item
    icon={({ color, size }) => <Icon name={icon} color={color} size={size} />}
    label={label}
    onPress={onPress}
  />
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  drawerContent: {
    flex: 1,
  },
  userInfoSection: {
    paddingLeft: 20,
    paddingVertical: 20,
  },
  userInfo: {
    flexDirection: 'row',
    marginTop: 15,
  },
  userDetails: {
    marginLeft: 15,
    flexDirection: 'column',
    justifyContent: 'center',
  },
  title: {
    fontSize: 16,
    marginTop: 3,
    fontWeight: 'bold',
  },
  caption: {
    fontSize: 14,
    lineHeight: 14,
  },
  drawerSection: {
    marginTop: 15,
  },
  bottomDrawerSection: {
    marginBottom: 15,
    borderTopColor: '#f4f4f4',
    borderTopWidth: 1,
  },
  preference: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
});
