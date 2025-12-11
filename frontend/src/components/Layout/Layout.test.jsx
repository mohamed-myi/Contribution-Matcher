import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Layout, AuthLayout } from './Layout';

describe('Layout', () => {
  it('renders children', () => {
    render(<Layout>Test content</Layout>);
    expect(screen.getByText('Test content')).toBeInTheDocument();
  });

  it('renders Header component', () => {
    render(<Layout>Content</Layout>);
    // Header should be present (checking for header element)
    const header = screen.getByRole('banner');
    expect(header).toBeInTheDocument();
  });

  it('renders main content area', () => {
    render(<Layout>Content</Layout>);
    const main = screen.getByRole('main');
    expect(main).toBeInTheDocument();
    expect(main).toHaveClass('layout-main');
  });

  it('renders background elements', () => {
    render(<Layout>Content</Layout>);
    const sandTexture = document.querySelector('.sand-texture');
    const desertLines = document.querySelector('.desert-lines');
    expect(sandTexture).toBeInTheDocument();
    expect(desertLines).toBeInTheDocument();
  });
});

describe('AuthLayout', () => {
  it('renders children', () => {
    render(<AuthLayout>Auth content</AuthLayout>);
    expect(screen.getByText('Auth content')).toBeInTheDocument();
  });

  it('renders main content area', () => {
    render(<AuthLayout>Content</AuthLayout>);
    const main = screen.getByRole('main');
    expect(main).toBeInTheDocument();
    expect(main).toHaveClass('auth-layout-main');
  });

  it('renders background elements', () => {
    render(<AuthLayout>Content</AuthLayout>);
    const sandTexture = document.querySelector('.sand-texture');
    const desertLines = document.querySelector('.desert-lines');
    expect(sandTexture).toBeInTheDocument();
    expect(desertLines).toBeInTheDocument();
  });

  it('does not render Header', () => {
    render(<AuthLayout>Content</AuthLayout>);
    const header = screen.queryByRole('banner');
    expect(header).not.toBeInTheDocument();
  });
});
