import React from 'react';
import renderer from 'react-test-renderer';
import { Button } from '../Button';

describe('Button Component Snapshots', () => {
  describe('Variant Snapshots', () => {
    it('renders primary variant correctly', () => {
      const tree = renderer.create(
        <Button variant="primary">Primary Button</Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders secondary variant correctly', () => {
      const tree = renderer.create(
        <Button variant="secondary">Secondary Button</Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders outline variant correctly', () => {
      const tree = renderer.create(
        <Button variant="outline">Outline Button</Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders text variant correctly', () => {
      const tree = renderer.create(
        <Button variant="text">Text Button</Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders danger variant correctly', () => {
      const tree = renderer.create(
        <Button variant="danger">Danger Button</Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });
  });

  describe('Size Snapshots', () => {
    it('renders small size correctly', () => {
      const tree = renderer.create(
        <Button size="small">Small Button</Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders medium size correctly', () => {
      const tree = renderer.create(
        <Button size="medium">Medium Button</Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders large size correctly', () => {
      const tree = renderer.create(
        <Button size="large">Large Button</Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });
  });

  describe('State Snapshots', () => {
    it('renders loading state correctly', () => {
      const tree = renderer.create(
        <Button loading>Loading Button</Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders disabled state correctly', () => {
      const tree = renderer.create(
        <Button disabled>Disabled Button</Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders with icon correctly', () => {
      const tree = renderer.create(
        <Button icon="check">Button with Icon</Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders full width correctly', () => {
      const tree = renderer.create(
        <Button fullWidth>Full Width Button</Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });
  });

  describe('Combined Props Snapshots', () => {
    it('renders primary large button with icon', () => {
      const tree = renderer.create(
        <Button variant="primary" size="large" icon="send">
          Send Message
        </Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders outline small button disabled', () => {
      const tree = renderer.create(
        <Button variant="outline" size="small" disabled>
          Disabled Outline
        </Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders danger button loading state', () => {
      const tree = renderer.create(
        <Button variant="danger" loading>
          Delete Item
        </Button>
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });
  });
});