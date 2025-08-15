import React, { useState, useEffect } from 'react';
import {
  Modal,
  View,
  Text,
  StyleSheet,
  ScrollView,
  Switch,
  TouchableOpacity,
  Platform,
} from 'react-native';
import DatePicker from 'react-native-date-picker';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors, typography } from '@theme';
import { NotificationPreferences } from '@services/notifications/types';
import { NotificationService } from '@services/notifications/NotificationService';

interface NotificationSettingsModalProps {
  visible: boolean;
  onClose: () => void;
}

export const NotificationSettingsModal: React.FC<
  NotificationSettingsModalProps
> = ({ visible, onClose }) => {
  const notificationService = NotificationService.getInstance();
  const [preferences, setPreferences] = useState<NotificationPreferences>(
    notificationService.getPreferences(),
  );
  const [showStartTimePicker, setShowStartTimePicker] = useState(false);
  const [showEndTimePicker, setShowEndTimePicker] = useState(false);

  const handleToggle = (key: keyof NotificationPreferences) => {
    if (typeof preferences[key] === 'boolean') {
      const updated = { ...preferences, [key]: !preferences[key] };
      setPreferences(updated);
    }
  };

  const handleDoNotDisturbToggle = () => {
    const updated = {
      ...preferences,
      doNotDisturb: {
        ...preferences.doNotDisturb,
        enabled: !preferences.doNotDisturb.enabled,
      },
    };
    setPreferences(updated);
  };

  const handleTimeChange = (type: 'start' | 'end', time: Date) => {
    const timeString = `${time.getHours().toString().padStart(2, '0')}:${time.getMinutes().toString().padStart(2, '0')}`;
    const updated = {
      ...preferences,
      doNotDisturb: {
        ...preferences.doNotDisturb,
        [type === 'start' ? 'startTime' : 'endTime']: timeString,
      },
    };
    setPreferences(updated);
  };

  const handleSave = async () => {
    await notificationService.savePreferences(preferences);
    onClose();
  };

  const getTimeFromString = (timeString: string): Date => {
    const [hours, minutes] = timeString.split(':').map(Number);
    const date = new Date();
    date.setHours(hours);
    date.setMinutes(minutes);
    return date;
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>Notification Settings</Text>
          <TouchableOpacity onPress={onClose}>
            <Icon name="close" size={24} color={colors.text} />
          </TouchableOpacity>
        </View>

        <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>General</Text>

            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={styles.settingLabel}>Enable Notifications</Text>
                <Text style={styles.settingDescription}>
                  Receive push notifications from AuraConnect
                </Text>
              </View>
              <Switch
                value={preferences.enabled}
                onValueChange={() => handleToggle('enabled')}
                trackColor={{ false: colors.border, true: colors.primary }}
                thumbColor={
                  Platform.OS === 'ios' ? colors.white : colors.surface
                }
              />
            </View>
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Notification Types</Text>

            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={styles.settingLabel}>Order Updates</Text>
                <Text style={styles.settingDescription}>
                  New orders, status changes, and customer requests
                </Text>
              </View>
              <Switch
                value={preferences.orderUpdates}
                onValueChange={() => handleToggle('orderUpdates')}
                trackColor={{ false: colors.border, true: colors.primary }}
                thumbColor={
                  Platform.OS === 'ios' ? colors.white : colors.surface
                }
                disabled={!preferences.enabled}
              />
            </View>

            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={styles.settingLabel}>Promotions</Text>
                <Text style={styles.settingDescription}>
                  Special offers and marketing messages
                </Text>
              </View>
              <Switch
                value={preferences.promotions}
                onValueChange={() => handleToggle('promotions')}
                trackColor={{ false: colors.border, true: colors.primary }}
                thumbColor={
                  Platform.OS === 'ios' ? colors.white : colors.surface
                }
                disabled={!preferences.enabled}
              />
            </View>
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Alert Preferences</Text>

            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={styles.settingLabel}>Sound</Text>
                <Text style={styles.settingDescription}>
                  Play notification sounds
                </Text>
              </View>
              <Switch
                value={preferences.sound}
                onValueChange={() => handleToggle('sound')}
                trackColor={{ false: colors.border, true: colors.primary }}
                thumbColor={
                  Platform.OS === 'ios' ? colors.white : colors.surface
                }
                disabled={!preferences.enabled}
              />
            </View>

            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={styles.settingLabel}>Vibration</Text>
                <Text style={styles.settingDescription}>
                  Vibrate on notifications
                </Text>
              </View>
              <Switch
                value={preferences.vibration}
                onValueChange={() => handleToggle('vibration')}
                trackColor={{ false: colors.border, true: colors.primary }}
                thumbColor={
                  Platform.OS === 'ios' ? colors.white : colors.surface
                }
                disabled={!preferences.enabled}
              />
            </View>
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Do Not Disturb</Text>

            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={styles.settingLabel}>Enable Do Not Disturb</Text>
                <Text style={styles.settingDescription}>
                  Silence notifications during specified hours
                </Text>
              </View>
              <Switch
                value={preferences.doNotDisturb.enabled}
                onValueChange={handleDoNotDisturbToggle}
                trackColor={{ false: colors.border, true: colors.primary }}
                thumbColor={
                  Platform.OS === 'ios' ? colors.white : colors.surface
                }
                disabled={!preferences.enabled}
              />
            </View>

            {preferences.doNotDisturb.enabled && (
              <>
                <TouchableOpacity
                  style={styles.timeRow}
                  onPress={() => setShowStartTimePicker(true)}>
                  <Text style={styles.timeLabel}>Start Time</Text>
                  <View style={styles.timeValue}>
                    <Text style={styles.timeText}>
                      {preferences.doNotDisturb.startTime}
                    </Text>
                    <Icon
                      name="chevron-right"
                      size={20}
                      color={colors.textSecondary}
                    />
                  </View>
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.timeRow}
                  onPress={() => setShowEndTimePicker(true)}>
                  <Text style={styles.timeLabel}>End Time</Text>
                  <View style={styles.timeValue}>
                    <Text style={styles.timeText}>
                      {preferences.doNotDisturb.endTime}
                    </Text>
                    <Icon
                      name="chevron-right"
                      size={20}
                      color={colors.textSecondary}
                    />
                  </View>
                </TouchableOpacity>
              </>
            )}
          </View>
        </ScrollView>

        <View style={styles.footer}>
          <TouchableOpacity
            style={[styles.button, styles.cancelButton]}
            onPress={onClose}>
            <Text style={styles.cancelButtonText}>Cancel</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.button, styles.saveButton]}
            onPress={handleSave}>
            <Text style={styles.saveButtonText}>Save</Text>
          </TouchableOpacity>
        </View>
      </View>

      <DatePicker
        modal
        open={showStartTimePicker}
        date={getTimeFromString(preferences.doNotDisturb.startTime)}
        mode="time"
        onConfirm={date => {
          handleTimeChange('start', date);
          setShowStartTimePicker(false);
        }}
        onCancel={() => setShowStartTimePicker(false)}
      />

      <DatePicker
        modal
        open={showEndTimePicker}
        date={getTimeFromString(preferences.doNotDisturb.endTime)}
        mode="time"
        onConfirm={date => {
          handleTimeChange('end', date);
          setShowEndTimePicker(false);
        }}
        onCancel={() => setShowEndTimePicker(false)}
      />
    </Modal>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: {
    ...typography.title,
  },
  content: {
    flex: 1,
  },
  section: {
    paddingVertical: 16,
  },
  sectionTitle: {
    ...typography.subtitle,
    fontWeight: '600',
    paddingHorizontal: 16,
    marginBottom: 12,
    color: colors.primary,
  },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  settingInfo: {
    flex: 1,
    marginRight: 16,
  },
  settingLabel: {
    ...typography.body,
    fontWeight: '500',
    marginBottom: 4,
  },
  settingDescription: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  timeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  timeLabel: {
    ...typography.body,
  },
  timeValue: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  timeText: {
    ...typography.body,
    color: colors.primary,
    marginRight: 8,
  },
  footer: {
    flexDirection: 'row',
    padding: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  button: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  cancelButton: {
    marginRight: 8,
    backgroundColor: colors.surface,
  },
  saveButton: {
    marginLeft: 8,
    backgroundColor: colors.primary,
  },
  cancelButtonText: {
    ...typography.button,
    color: colors.text,
  },
  saveButtonText: {
    ...typography.button,
    color: colors.white,
  },
});
