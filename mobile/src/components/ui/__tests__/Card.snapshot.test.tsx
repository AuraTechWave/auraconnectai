import React from 'react';
import renderer from 'react-test-renderer';
import { Text } from 'react-native';
import { Card, CardHeader, CardContent, CardFooter } from '../Card';
import { Button } from '../Button';

describe('Card Component Snapshots', () => {
  describe('Variant Snapshots', () => {
    it('renders elevated variant correctly', () => {
      const tree = renderer.create(
        <Card variant="elevated">
          <CardContent>
            <Text>Elevated Card Content</Text>
          </CardContent>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders outlined variant correctly', () => {
      const tree = renderer.create(
        <Card variant="outlined">
          <CardContent>
            <Text>Outlined Card Content</Text>
          </CardContent>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders filled variant correctly', () => {
      const tree = renderer.create(
        <Card variant="filled">
          <CardContent>
            <Text>Filled Card Content</Text>
          </CardContent>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });
  });

  describe('Padding Snapshots', () => {
    it('renders with no padding correctly', () => {
      const tree = renderer.create(
        <Card padding="none">
          <Text>No Padding Card</Text>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders with small padding correctly', () => {
      const tree = renderer.create(
        <Card padding="small">
          <Text>Small Padding Card</Text>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders with medium padding correctly', () => {
      const tree = renderer.create(
        <Card padding="medium">
          <Text>Medium Padding Card</Text>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders with large padding correctly', () => {
      const tree = renderer.create(
        <Card padding="large">
          <Text>Large Padding Card</Text>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });
  });

  describe('Card Structure Snapshots', () => {
    it('renders card with header correctly', () => {
      const tree = renderer.create(
        <Card>
          <CardHeader>
            <Text>Card Title</Text>
          </CardHeader>
          <CardContent>
            <Text>Card Body Content</Text>
          </CardContent>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders card with footer correctly', () => {
      const tree = renderer.create(
        <Card>
          <CardContent>
            <Text>Card Body Content</Text>
          </CardContent>
          <CardFooter>
            <Button size="small">Action</Button>
          </CardFooter>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders complete card structure correctly', () => {
      const tree = renderer.create(
        <Card variant="elevated">
          <CardHeader>
            <Text style={{ fontSize: 18, fontWeight: 'bold' }}>
              Complete Card Example
            </Text>
          </CardHeader>
          <CardContent>
            <Text>
              This is a complete card with header, content, and footer sections.
            </Text>
          </CardContent>
          <CardFooter>
            <Button variant="text" size="small">Cancel</Button>
            <Button variant="primary" size="small">Save</Button>
          </CardFooter>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });
  });

  describe('Interactive Card Snapshots', () => {
    it('renders pressable card correctly', () => {
      const tree = renderer.create(
        <Card onPress={() => {}} variant="outlined">
          <CardContent>
            <Text>Pressable Card</Text>
          </CardContent>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders pressable elevated card with custom style', () => {
      const tree = renderer.create(
        <Card 
          onPress={() => {}} 
          variant="elevated"
          style={{ marginHorizontal: 20 }}
        >
          <CardContent>
            <Text>Custom Styled Pressable Card</Text>
          </CardContent>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });
  });

  describe('Theme Variant Combinations', () => {
    it('renders outlined card with header and footer', () => {
      const tree = renderer.create(
        <Card variant="outlined" padding="small">
          <CardHeader>
            <Text style={{ fontWeight: '600' }}>Settings</Text>
          </CardHeader>
          <CardContent>
            <Text>Configure your preferences</Text>
          </CardContent>
          <CardFooter>
            <Button variant="outline" size="small">Reset</Button>
            <Button variant="primary" size="small">Apply</Button>
          </CardFooter>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders filled card with large padding', () => {
      const tree = renderer.create(
        <Card variant="filled" padding="large">
          <CardContent>
            <Text style={{ fontSize: 24, fontWeight: 'bold', marginBottom: 8 }}>
              Welcome Back!
            </Text>
            <Text>
              Your dashboard is ready with the latest updates.
            </Text>
          </CardContent>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders elevated pressable card with icon content', () => {
      const tree = renderer.create(
        <Card variant="elevated" onPress={() => {}}>
          <CardContent>
            <Text style={{ fontSize: 16, fontWeight: '500' }}>
              Order #12345
            </Text>
            <Text style={{ color: '#666', marginTop: 4 }}>
              2 items • $25.99
            </Text>
          </CardContent>
        </Card>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });
  });
});