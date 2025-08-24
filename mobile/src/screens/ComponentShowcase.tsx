import React from 'react';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  Switch,
} from 'react-native';
import {
  Button,
  Card,
  CardHeader,
  CardContent,
  CardFooter,
  Input,
  Badge,
  BadgeContainer,
  Avatar,
  AvatarGroup,
} from '../components/ui';
import { designSystem } from '../constants/designSystem';

export const ComponentShowcase = () => {
  const [switchValue, setSwitchValue] = React.useState(false);
  const [inputValue, setInputValue] = React.useState('');

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false}>
        <Text style={styles.title}>Component Showcase</Text>

        {/* Buttons Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Buttons</Text>
          
          <View style={styles.componentRow}>
            <Button variant="primary" onPress={() => console.log('Primary')}>
              Primary Button
            </Button>
            <Button variant="secondary" onPress={() => console.log('Secondary')}>
              Secondary
            </Button>
          </View>

          <View style={styles.componentRow}>
            <Button variant="outline" onPress={() => console.log('Outline')}>
              Outline
            </Button>
            <Button variant="text" onPress={() => console.log('Text')}>
              Text Button
            </Button>
          </View>

          <View style={styles.componentRow}>
            <Button variant="primary" size="small" onPress={() => {}}>
              Small
            </Button>
            <Button variant="primary" size="large" onPress={() => {}}>
              Large
            </Button>
          </View>

          <View style={styles.componentRow}>
            <Button variant="primary" disabled onPress={() => {}}>
              Disabled
            </Button>
            <Button variant="primary" loading onPress={() => {}}>
              Loading
            </Button>
          </View>
        </View>

        {/* Input Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Inputs</Text>
          
          <Input
            label="Email"
            placeholder="Enter your email"
            value={inputValue}
            onChangeText={setInputValue}
            keyboardType="email-address"
          />

          <Input
            label="Password"
            placeholder="Enter password"
            secureTextEntry
            style={{ marginTop: 16 }}
          />

          <Input
            label="With Error"
            placeholder="This field has an error"
            error="This field is required"
            style={{ marginTop: 16 }}
          />

          <Input
            label="Disabled"
            placeholder="Disabled input"
            disabled
            style={{ marginTop: 16 }}
          />
        </View>

        {/* Cards Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Cards</Text>
          
          <Card variant="elevated">
            <CardHeader title="Elevated Card" subtitle="With shadow" />
            <CardContent>
              <Text style={styles.cardText}>
                This is an elevated card with a shadow effect.
              </Text>
            </CardContent>
            <CardFooter>
              <Button variant="text" size="small" onPress={() => {}}>
                Action
              </Button>
            </CardFooter>
          </Card>

          <Card variant="outlined" style={{ marginTop: 16 }}>
            <CardHeader title="Outlined Card" />
            <CardContent>
              <Text style={styles.cardText}>
                This is an outlined card with a border.
              </Text>
            </CardContent>
          </Card>
        </View>

        {/* Badges Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Badges</Text>
          
          <BadgeContainer>
            <Badge variant="primary">Primary</Badge>
            <Badge variant="secondary">Secondary</Badge>
            <Badge variant="success">Success</Badge>
            <Badge variant="warning">Warning</Badge>
            <Badge variant="error">Error</Badge>
          </BadgeContainer>

          <BadgeContainer style={{ marginTop: 16 }}>
            <Badge variant="primary" size="small">Small</Badge>
            <Badge variant="primary" size="large">Large</Badge>
          </BadgeContainer>
        </View>

        {/* Avatars Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Avatars</Text>
          
          <View style={styles.componentRow}>
            <Avatar
              source={{ uri: 'https://i.pravatar.cc/150?img=1' }}
              size="small"
            />
            <Avatar
              source={{ uri: 'https://i.pravatar.cc/150?img=2' }}
              size="medium"
            />
            <Avatar
              source={{ uri: 'https://i.pravatar.cc/150?img=3' }}
              size="large"
            />
          </View>

          <View style={styles.componentRow}>
            <Avatar name="John Doe" size="medium" />
            <Avatar name="Jane Smith" size="medium" />
          </View>

          <AvatarGroup
            avatars={[
              { source: { uri: 'https://i.pravatar.cc/150?img=4' } },
              { source: { uri: 'https://i.pravatar.cc/150?img=5' } },
              { source: { uri: 'https://i.pravatar.cc/150?img=6' } },
              { source: { uri: 'https://i.pravatar.cc/150?img=7' } },
              { source: { uri: 'https://i.pravatar.cc/150?img=8' } },
            ]}
            max={4}
            style={{ marginTop: 16 }}
          />
        </View>

        {/* Design Tokens Preview */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Design Tokens</Text>
          
          <Text style={styles.subsectionTitle}>Colors</Text>
          <View style={styles.colorGrid}>
            {Object.entries(designSystem.colors.semantic).map(([key, value]) => (
              <View key={key} style={styles.colorItem}>
                <View style={[styles.colorSwatch, { backgroundColor: value }]} />
                <Text style={styles.colorLabel}>{key}</Text>
              </View>
            ))}
          </View>

          <Text style={styles.subsectionTitle}>Typography</Text>
          {Object.entries(designSystem.typography.fontSize).map(([key, value]) => (
            <Text key={key} style={[styles.typographyExample, { fontSize: value }]}>
              {key}: {value}
            </Text>
          ))}

          <Text style={styles.subsectionTitle}>Spacing</Text>
          <View style={styles.spacingContainer}>
            {Object.entries(designSystem.spacing).map(([key, value]) => (
              <View key={key} style={styles.spacingItem}>
                <View style={[styles.spacingBox, { width: value, height: value }]} />
                <Text style={styles.spacingLabel}>{key}</Text>
              </View>
            ))}
          </View>
        </View>

        <View style={{ height: 50 }} />
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: designSystem.colors.background.primary,
  },
  title: {
    fontSize: designSystem.typography.fontSize['3xl'],
    fontWeight: designSystem.typography.fontWeight.bold as any,
    color: designSystem.colors.text.primary,
    marginHorizontal: designSystem.spacing[4],
    marginTop: designSystem.spacing[4],
    marginBottom: designSystem.spacing[6],
  },
  section: {
    paddingHorizontal: designSystem.spacing[4],
    marginBottom: designSystem.spacing[8],
  },
  sectionTitle: {
    fontSize: designSystem.typography.fontSize.xl,
    fontWeight: designSystem.typography.fontWeight.semibold as any,
    color: designSystem.colors.text.primary,
    marginBottom: designSystem.spacing[4],
  },
  subsectionTitle: {
    fontSize: designSystem.typography.fontSize.lg,
    fontWeight: designSystem.typography.fontWeight.medium as any,
    color: designSystem.colors.text.secondary,
    marginTop: designSystem.spacing[4],
    marginBottom: designSystem.spacing[3],
  },
  componentRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    marginVertical: designSystem.spacing[2],
  },
  cardText: {
    fontSize: designSystem.typography.fontSize.base,
    color: designSystem.colors.text.secondary,
    lineHeight: designSystem.typography.fontSize.base * designSystem.typography.lineHeight.normal,
  },
  colorGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: designSystem.spacing[2],
  },
  colorItem: {
    alignItems: 'center',
    marginRight: designSystem.spacing[3],
    marginBottom: designSystem.spacing[3],
  },
  colorSwatch: {
    width: 60,
    height: 60,
    borderRadius: designSystem.borders.radius.md,
    marginBottom: designSystem.spacing[1],
  },
  colorLabel: {
    fontSize: designSystem.typography.fontSize.xs,
    color: designSystem.colors.text.secondary,
  },
  typographyExample: {
    color: designSystem.colors.text.primary,
    marginVertical: designSystem.spacing[1],
  },
  spacingContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: designSystem.spacing[3],
  },
  spacingItem: {
    alignItems: 'center',
  },
  spacingBox: {
    backgroundColor: designSystem.colors.semantic.primary,
    marginBottom: designSystem.spacing[1],
  },
  spacingLabel: {
    fontSize: designSystem.typography.fontSize.xs,
    color: designSystem.colors.text.secondary,
  },
});