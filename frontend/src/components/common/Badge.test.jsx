import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge, DifficultyBadge, ScoreBadge, TechBadge } from './Badge';

describe('Badge', () => {
  it('renders children', () => {
    render(<Badge>Badge text</Badge>);
    expect(screen.getByText('Badge text')).toBeInTheDocument();
  });

  it('applies default variant', () => {
    render(<Badge>Default</Badge>);
    expect(screen.getByText('Default')).toHaveClass('badge-default');
  });

  it('applies variant classes', () => {
    const { rerender } = render(<Badge variant="success">Success</Badge>);
    expect(screen.getByText('Success')).toHaveClass('badge-success');

    rerender(<Badge variant="warning">Warning</Badge>);
    expect(screen.getByText('Warning')).toHaveClass('badge-warning');
  });

  it('applies size classes', () => {
    const { rerender } = render(<Badge size="sm">Small</Badge>);
    expect(screen.getByText('Small')).toHaveClass('badge-sm');

    rerender(<Badge size="lg">Large</Badge>);
    expect(screen.getByText('Large')).toHaveClass('badge-lg');
  });

  it('applies custom className', () => {
    render(<Badge className="custom-class">Custom</Badge>);
    expect(screen.getByText('Custom')).toHaveClass('custom-class');
  });
});

describe('DifficultyBadge', () => {
  it('renders difficulty text', () => {
    render(<DifficultyBadge difficulty="beginner" />);
    expect(screen.getByText('beginner')).toBeInTheDocument();
  });

  it('maps beginner difficulty correctly', () => {
    render(<DifficultyBadge difficulty="beginner" />);
    expect(screen.getByText('beginner')).toHaveClass('badge-beginner');
  });

  it('maps intermediate difficulty correctly', () => {
    render(<DifficultyBadge difficulty="intermediate" />);
    expect(screen.getByText('intermediate')).toHaveClass('badge-intermediate');
  });

  it('maps advanced difficulty correctly', () => {
    render(<DifficultyBadge difficulty="advanced" />);
    expect(screen.getByText('advanced')).toHaveClass('badge-advanced');
  });

  it('maps "good first issue" to beginner', () => {
    render(<DifficultyBadge difficulty="good first issue" />);
    expect(screen.getByText('good first issue')).toHaveClass('badge-beginner');
  });

  it('handles unknown difficulty', () => {
    render(<DifficultyBadge difficulty="unknown" />);
    expect(screen.getByText('unknown')).toHaveClass('badge-default');
  });

  it('handles null difficulty', () => {
    render(<DifficultyBadge difficulty={null} />);
    expect(screen.getByText('Unknown')).toBeInTheDocument();
  });
});

describe('ScoreBadge', () => {
  it('renders score percentage', () => {
    render(<ScoreBadge score={85} />);
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('rounds score correctly', () => {
    render(<ScoreBadge score={85.7} />);
    expect(screen.getByText('86%')).toBeInTheDocument();
  });

  it('applies success variant for score >= 80', () => {
    render(<ScoreBadge score={85} />);
    expect(screen.getByText('85%')).toHaveClass('badge-success');
  });

  it('applies warning variant for score >= 60', () => {
    render(<ScoreBadge score={65} />);
    expect(screen.getByText('65%')).toHaveClass('badge-warning');
  });

  it('applies info variant for score >= 40', () => {
    render(<ScoreBadge score={45} />);
    expect(screen.getByText('45%')).toHaveClass('badge-info');
  });

  it('applies muted variant for score < 40', () => {
    render(<ScoreBadge score={30} />);
    expect(screen.getByText('30%')).toHaveClass('badge-muted');
  });
});

describe('TechBadge', () => {
  it('renders tech name', () => {
    render(<TechBadge tech="Python" />);
    expect(screen.getByText('Python')).toBeInTheDocument();
  });

  it('applies tech variant', () => {
    render(<TechBadge tech="JavaScript" />);
    expect(screen.getByText('JavaScript')).toHaveClass('badge-tech');
  });

  it('defaults to small size', () => {
    render(<TechBadge tech="React" />);
    expect(screen.getByText('React')).toHaveClass('badge-sm');
  });
});
