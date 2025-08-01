import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

describe('App', () => {
  test('renders without crashing', () => {
    render(<App />);
  });

  test('renders header with restaurant name', () => {
    render(<App />);
    const headerElement = screen.getByText(/AuraConnect Restaurant/i);
    expect(headerElement).toBeInTheDocument();
  });

  test('renders menu link', () => {
    render(<App />);
    const menuLinks = screen.getAllByText(/Menu/i);
    expect(menuLinks.length).toBeGreaterThan(0);
  });

  test('renders login button when not authenticated', () => {
    render(<App />);
    const loginButton = screen.getByRole('link', { name: /Login/i });
    expect(loginButton).toBeInTheDocument();
  });
});
