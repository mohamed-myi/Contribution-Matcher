import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { Layout, AuthLayout } from './Layout';
import { renderWithProviders } from '../../test/test-utils';

describe('Layout', () => {
  it('renders children', () => {
    renderWithProviders(<Layout>Test content</Layout>);
    expect(screen.getByText('Test content')).toBeInTheDocument();
  });

  it('renders Header component', () => {
    renderWithProviders(<Layout>Content</Layout>);
    // Header should be present (checking for header element)
    const header = screen.getByRole('banner');
    expect(header).toBeInTheDocument();
  });

  it('renders main content area', () => {
    renderWithProviders(<Layout>Content</Layout>);
    const main = screen.getByRole('main');
    expect(main).toBeInTheDocument();
    expect(main).toHaveClass('layout-main');
  });

  it('renders background elements', () => {
    renderWithProviders(<Layout>Content</Layout>);
    const sandTexture = document.querySelector('.sand-texture');
    const desertLines = document.querySelector('.desert-lines');
    expect(sandTexture).toBeInTheDocument();
    expect(desertLines).toBeInTheDocument();
  });
});

describe('AuthLayout', () => {
  it('renders children', () => {
    renderWithProviders(<AuthLayout>Auth content</AuthLayout>);
    expect(screen.getByText('Auth content')).toBeInTheDocument();
  });

  it('renders main content area', () => {
    renderWithProviders(<AuthLayout>Content</AuthLayout>);
    const main = screen.getByRole('main');
    expect(main).toBeInTheDocument();
    expect(main).toHaveClass('auth-layout-main');
  });

  it('renders background elements', () => {
    renderWithProviders(<AuthLayout>Content</AuthLayout>);
    const sandTexture = document.querySelector('.sand-texture');
    const desertLines = document.querySelector('.desert-lines');
    expect(sandTexture).toBeInTheDocument();
    expect(desertLines).toBeInTheDocument();
  });

  it('does not render Header', () => {
    renderWithProviders(<AuthLayout>Content</AuthLayout>);
    const header = screen.queryByRole('banner');
    expect(header).not.toBeInTheDocument();
  });
});
