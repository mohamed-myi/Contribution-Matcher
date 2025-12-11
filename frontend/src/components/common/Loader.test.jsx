import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Loader, PageLoader, SkeletonLoader } from './Loader';

describe('Loader', () => {
  it('renders with default size', () => {
    render(<Loader />);
    const loader = screen.getByRole('status');
    expect(loader).toBeInTheDocument();
    expect(loader).toHaveClass('loader-md');
  });

  it('applies size classes', () => {
    const { rerender } = render(<Loader size="sm" />);
    expect(screen.getByRole('status')).toHaveClass('loader-sm');

    rerender(<Loader size="lg" />);
    expect(screen.getByRole('status')).toHaveClass('loader-lg');
  });

  it('has accessibility attributes', () => {
    render(<Loader />);
    const loader = screen.getByRole('status');
    expect(loader).toHaveAttribute('aria-label', 'Loading');
  });

  it('renders spinner SVG', () => {
    render(<Loader />);
    const svg = screen.getByRole('status').querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<Loader className="custom-loader" />);
    expect(screen.getByRole('status')).toHaveClass('custom-loader');
  });
});

describe('PageLoader', () => {
  it('renders with default message', () => {
    render(<PageLoader />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('renders with custom message', () => {
    render(<PageLoader message="Please wait" />);
    expect(screen.getByText('Please wait')).toBeInTheDocument();
  });

  it('renders Loader component', () => {
    render(<PageLoader />);
    const loader = screen.getByRole('status');
    expect(loader).toBeInTheDocument();
    expect(loader).toHaveClass('loader-lg');
  });
});

describe('SkeletonLoader', () => {
  it('renders skeleton element', () => {
    const { container } = render(<SkeletonLoader />);
    const skeleton = container.querySelector('.skeleton');
    expect(skeleton).toBeInTheDocument();
    expect(skeleton).toHaveClass('skeleton');
  });

  it('applies variant class', () => {
    const { container } = render(<SkeletonLoader variant="text" />);
    const skeleton = container.querySelector('.skeleton');
    expect(skeleton).toHaveClass('skeleton-text');
  });

  it('applies custom width and height', () => {
    const { container } = render(<SkeletonLoader width="200px" height="20px" />);
    const skeleton = container.querySelector('.skeleton');
    expect(skeleton).toHaveStyle({ width: '200px', height: '20px' });
  });

  it('uses default dimensions for text variant', () => {
    const { container } = render(<SkeletonLoader variant="text" />);
    const skeleton = container.querySelector('.skeleton');
    expect(skeleton).toHaveStyle({ width: '100%', height: '1em' });
  });

  it('applies custom className', () => {
    const { container } = render(<SkeletonLoader className="custom-skeleton" />);
    const skeleton = container.querySelector('.skeleton');
    expect(skeleton).toHaveClass('custom-skeleton');
  });
});
