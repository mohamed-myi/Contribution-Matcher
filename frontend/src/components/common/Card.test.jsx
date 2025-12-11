import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Card, CardHeader, CardBody, CardFooter } from './Card';

describe('Card', () => {
  it('renders children', () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText('Card content')).toBeInTheDocument();
  });

  it('applies default variant', () => {
    const { container } = render(<Card>Test</Card>);
    const card = container.querySelector('.card');
    expect(card).toHaveClass('card-default');
  });

  it('applies variant classes', () => {
    const { container, rerender } = render(<Card variant="glass">Glass</Card>);
    let card = container.querySelector('.card');
    expect(card).toHaveClass('card-glass');

    rerender(<Card variant="outlined">Outlined</Card>);
    card = container.querySelector('.card');
    expect(card).toHaveClass('card-outlined');
  });

  it('applies padding classes', () => {
    const { container, rerender } = render(<Card padding="sm">Small</Card>);
    let card = container.querySelector('.card');
    expect(card).toHaveClass('card-padding-sm');

    rerender(<Card padding="lg">Large</Card>);
    card = container.querySelector('.card');
    expect(card).toHaveClass('card-padding-lg');
  });

  it('applies hover class when hover prop is true', () => {
    const { container } = render(<Card hover>Hover</Card>);
    const card = container.querySelector('.card');
    expect(card).toHaveClass('card-hover');
  });

  it('applies glow class when glow prop is true', () => {
    const { container } = render(<Card glow>Glow</Card>);
    const card = container.querySelector('.card');
    expect(card).toHaveClass('card-glow');
  });

  it('handles click events', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    const { container } = render(<Card onClick={handleClick}>Clickable</Card>);
    
    const card = container.querySelector('.card');
    await user.click(card);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('has button role when onClick is provided', () => {
    render(<Card onClick={() => {}}>Clickable</Card>);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('has tabIndex when onClick is provided', () => {
    render(<Card onClick={() => {}}>Clickable</Card>);
    expect(screen.getByRole('button')).toHaveAttribute('tabIndex', '0');
  });

  it('applies custom className', () => {
    const { container } = render(<Card className="custom-class">Custom</Card>);
    const card = container.querySelector('.card');
    expect(card).toHaveClass('custom-class');
  });
});

describe('CardHeader', () => {
  it('renders children', () => {
    render(<CardHeader>Header content</CardHeader>);
    expect(screen.getByText('Header content')).toBeInTheDocument();
  });

  it('applies card-header class', () => {
    render(<CardHeader>Header</CardHeader>);
    expect(screen.getByText('Header')).toHaveClass('card-header');
  });
});

describe('CardBody', () => {
  it('renders children', () => {
    render(<CardBody>Body content</CardBody>);
    expect(screen.getByText('Body content')).toBeInTheDocument();
  });

  it('applies card-body class', () => {
    render(<CardBody>Body</CardBody>);
    expect(screen.getByText('Body')).toHaveClass('card-body');
  });
});

describe('CardFooter', () => {
  it('renders children', () => {
    render(<CardFooter>Footer content</CardFooter>);
    expect(screen.getByText('Footer content')).toBeInTheDocument();
  });

  it('applies card-footer class', () => {
    render(<CardFooter>Footer</CardFooter>);
    expect(screen.getByText('Footer')).toHaveClass('card-footer');
  });
});
