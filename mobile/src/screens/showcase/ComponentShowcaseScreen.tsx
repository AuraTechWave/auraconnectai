import React, { useState } from 'react';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  SafeAreaView,
} from 'react-native';
import {
  Button,
  Input,
  Badge,
  BadgeContainer,
  Card,
  Avatar,
  colors,
  spacing,
  typography,
} from '../../components/ui';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';

export const ComponentShowcaseScreen: React.FC = () => {
  const [inputValue, setInputValue] = useState('');
  const [emailValue, setEmailValue] = useState('');
  const [passwordValue, setPasswordValue] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleButtonPress = () => {
    setIsLoading(true);
    setTimeout(() => setIsLoading(false), 2000);
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false}>
        <View style={styles.content}>
          <Text style={styles.title}>AuraConnect Component Showcase</Text>
          
          {/* Buttons Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Buttons</Text>
            
            <Text style={styles.subsectionTitle}>Variants</Text>
            <View style={styles.row}>
              <Button title="Primary" variant="primary" />
              <Button title="Secondary" variant="secondary" />
              <Button title="Tertiary" variant="tertiary" />
            </View>
            <View style={styles.row}>
              <Button title="Danger" variant="danger" />
              <Button title="Ghost" variant="ghost" />
              <Button title="Outline" variant="outline" />
            </View>
            
            <Text style={styles.subsectionTitle}>Sizes</Text>
            <View style={styles.row}>
              <Button title="Small" size="small" />
              <Button title="Medium" size="medium" />
              <Button title="Large" size="large" />
            </View>
            
            <Text style={styles.subsectionTitle}>With Icons</Text>
            <View style={styles.row}>
              <Button 
                title="Left Icon" 
                icon="check" 
                iconPosition="left" 
              />
              <Button 
                title="Right Icon" 
                icon="arrow-right" 
                iconPosition="right" 
              />
            </View>
            
            <Text style={styles.subsectionTitle}>States</Text>
            <View style={styles.row}>
              <Button 
                title="Loading" 
                loading={isLoading}
                onPress={handleButtonPress}
              />
              <Button title="Disabled" disabled />
            </View>
            
            <Button 
              title="Full Width Button" 
              variant="primary"
              fullWidth
              style={styles.spacingTop}
            />
          </View>

          {/* Inputs Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Inputs</Text>
            
            <Text style={styles.subsectionTitle}>Variants</Text>
            <Input
              label="Outlined Input"
              placeholder="Enter text"
              value={inputValue}
              onChangeText={setInputValue}
              variant="outlined"
              style={styles.input}
            />
            
            <Input
              label="Filled Input"
              placeholder="Enter text"
              variant="filled"
              style={styles.input}
            />
            
            <Input
              label="Underlined Input"
              placeholder="Enter text"
              variant="underlined"
              style={styles.input}
            />
            
            <Text style={styles.subsectionTitle}>With Icons & Validation</Text>
            <Input
              label="Email"
              placeholder="Enter your email"
              value={emailValue}
              onChangeText={setEmailValue}
              leftIcon="email"
              keyboardType="email-address"
              autoCapitalize="none"
              helper="We'll never share your email"
              style={styles.input}
            />
            
            <Input
              label="Password"
              placeholder="Enter password"
              value={passwordValue}
              onChangeText={setPasswordValue}
              leftIcon="lock"
              rightIcon={showPassword ? "eye-off" : "eye"}
              onRightIconPress={() => setShowPassword(!showPassword)}
              secureTextEntry={!showPassword}
              error={passwordValue && passwordValue.length < 8 ? "Password must be at least 8 characters" : undefined}
              style={styles.input}
            />
            
            <Input
              label="Disabled Input"
              placeholder="Cannot edit"
              disabled
              value="Disabled value"
              style={styles.input}
            />
          </View>

          {/* Badges Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Badges</Text>
            
            <Text style={styles.subsectionTitle}>Variants</Text>
            <View style={styles.row}>
              <Badge label="Default" variant="default" />
              <Badge label="3" variant="primary" />
              <Badge label="New" variant="secondary" />
              <Badge label="✓" variant="success" />
              <Badge label="!" variant="warning" />
              <Badge label="X" variant="error" />
              <Badge label="i" variant="info" />
            </View>
            
            <Text style={styles.subsectionTitle}>Sizes</Text>
            <View style={styles.row}>
              <Badge label="S" size="small" variant="primary" />
              <Badge label="M" size="medium" variant="primary" />
              <Badge label="L" size="large" variant="primary" />
            </View>
            
            <Text style={styles.subsectionTitle}>Dot Badges</Text>
            <View style={styles.row}>
              <Badge dot size="small" variant="error" />
              <Badge dot size="medium" variant="error" />
              <Badge dot size="large" variant="error" />
            </View>
            
            <Text style={styles.subsectionTitle}>Badge Containers</Text>
            <View style={styles.row}>
              <BadgeContainer 
                badge={<Badge label="3" variant="error" size="small" />}
                position="top-right"
              >
                <MaterialCommunityIcons name="bell" size={32} color={colors.neutral[700]} />
              </BadgeContainer>
              
              <BadgeContainer 
                badge={<Badge dot variant="success" />}
                position="top-left"
              >
                <Avatar name="JD" size="medium" />
              </BadgeContainer>
              
              <BadgeContainer 
                badge={<Badge label="99+" variant="primary" size="small" />}
                position="bottom-right"
              >
                <MaterialCommunityIcons name="message" size={32} color={colors.neutral[700]} />
              </BadgeContainer>
            </View>
          </View>

          {/* Cards Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Cards</Text>
            
            <Card style={styles.card}>
              <Card.Header>
                <Text style={styles.cardTitle}>Simple Card</Text>
              </Card.Header>
              <Card.Content>
                <Text style={styles.cardText}>
                  This is a basic card with header and content sections.
                </Text>
              </Card.Content>
            </Card>
            
            <Card onPress={() => console.log('Card pressed')} style={styles.card}>
              <Card.Header>
                <View style={styles.cardHeaderRow}>
                  <Text style={styles.cardTitle}>Interactive Card</Text>
                  <Badge label="New" variant="success" size="small" />
                </View>
              </Card.Header>
              <Card.Content>
                <Text style={styles.cardText}>
                  This card is pressable and includes a badge in the header.
                </Text>
              </Card.Content>
              <Card.Footer>
                <View style={styles.cardFooterRow}>
                  <Button title="Cancel" variant="ghost" size="small" />
                  <Button title="Confirm" variant="primary" size="small" />
                </View>
              </Card.Footer>
            </Card>
          </View>

          {/* Avatars Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Avatars</Text>
            
            <Text style={styles.subsectionTitle}>Sizes</Text>
            <View style={styles.row}>
              <Avatar name="XS" size="xsmall" />
              <Avatar name="SM" size="small" />
              <Avatar name="MD" size="medium" />
              <Avatar name="LG" size="large" />
              <Avatar name="XL" size="xlarge" />
            </View>
            
            <Text style={styles.subsectionTitle}>With Images</Text>
            <View style={styles.row}>
              <Avatar 
                source={{ uri: 'https://i.pravatar.cc/150?img=1' }}
                size="medium"
              />
              <Avatar 
                source={{ uri: 'https://i.pravatar.cc/150?img=2' }}
                size="medium"
              />
              <Avatar 
                source={{ uri: 'https://i.pravatar.cc/150?img=3' }}
                size="medium"
              />
            </View>
            
            <Text style={styles.subsectionTitle}>Custom Colors</Text>
            <View style={styles.row}>
              <Avatar 
                name="JD" 
                size="medium" 
                backgroundColor={colors.primary[500]}
              />
              <Avatar 
                name="AS" 
                size="medium" 
                backgroundColor={colors.secondary[500]}
              />
              <Avatar 
                name="MK" 
                size="medium" 
                backgroundColor={colors.accent[500]}
              />
            </View>
          </View>

          {/* Accessibility Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Accessibility Features</Text>
            <Text style={styles.description}>
              All components include comprehensive accessibility support:
            </Text>
            <View style={styles.list}>
              <Text style={styles.listItem}>• Screen reader labels and hints</Text>
              <Text style={styles.listItem}>• Proper role assignments</Text>
              <Text style={styles.listItem}>• State announcements</Text>
              <Text style={styles.listItem}>• Minimum touch targets (44x44)</Text>
              <Text style={styles.listItem}>• High contrast support</Text>
            </View>
            
            <Button
              title="Test Accessibility"
              variant="primary"
              icon="account-voice"
              accessibilityLabel="Test accessibility features"
              accessibilityHint="Activates screen reader test"
              style={styles.spacingTop}
            />
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background.primary,
  },
  content: {
    padding: spacing.lg,
  },
  title: {
    fontSize: typography.fontSize.h3,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
    marginBottom: spacing.xl,
    textAlign: 'center',
  },
  section: {
    marginBottom: spacing.xxl,
  },
  sectionTitle: {
    fontSize: typography.fontSize.h5,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.text.primary,
    marginBottom: spacing.md,
  },
  subsectionTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.medium,
    color: colors.text.secondary,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  input: {
    marginBottom: spacing.md,
  },
  card: {
    marginBottom: spacing.md,
  },
  cardTitle: {
    fontSize: typography.fontSize.subtitle,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.text.primary,
  },
  cardText: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    lineHeight: typography.lineHeight.body,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardFooterRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: spacing.sm,
  },
  description: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    marginBottom: spacing.sm,
    lineHeight: typography.lineHeight.body,
  },
  list: {
    marginLeft: spacing.sm,
  },
  listItem: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    marginBottom: spacing.xs,
    lineHeight: typography.lineHeight.body,
  },
  spacingTop: {
    marginTop: spacing.md,
  },
});