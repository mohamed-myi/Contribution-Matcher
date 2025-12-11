import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import {
  SkeletonText,
  SkeletonBadge,
  SkeletonCard,
  SkeletonRow,
  SkeletonStatsCard,
  SkeletonProfile,
  SkeletonList,
  SkeletonProgressBar,
} from './Skeleton';

describe('SkeletonText', () => {
  it('renders single line by default', () => {
    const { container } = render(<SkeletonText />);
    const lines = container.querySelectorAll('.skeleton-text-line');
    expect(lines).toHaveLength(1);
  });

  it('renders multiple lines', () => {
    const { container } = render(<SkeletonText lines={3} />);
    const lines = container.querySelectorAll('.skeleton-text-line');
    expect(lines).toHaveLength(3);
  });

  it('applies custom width', () => {
    const { container } = render(<SkeletonText width="50%" />);
    const firstLine = container.querySelector('.skeleton-text-line');
    expect(firstLine).toHaveStyle({ width: '50%' });
  });

  it('last line is shorter when multiple lines', () => {
    const { container } = render(<SkeletonText lines={3} />);
    const lines = container.querySelectorAll('.skeleton-text-line');
    expect(lines[2]).toHaveStyle({ width: '80%' });
  });
});

describe('SkeletonBadge', () => {
  it('renders badge skeleton', () => {
    const { container } = render(<SkeletonBadge />);
    const badge = container.querySelector('.skeleton-badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass('skeleton-badge');
  });

  it('applies custom width', () => {
    const { container } = render(<SkeletonBadge width="100px" />);
    const badge = container.querySelector('.skeleton-badge');
    expect(badge).toHaveStyle({ width: '100px' });
  });
});

describe('SkeletonCard', () => {
  it('renders card skeleton structure', () => {
    const { container } = render(<SkeletonCard />);
    const wrapper = container.querySelector('.skeleton-card-wrapper');
    expect(wrapper).toBeInTheDocument();
    expect(wrapper).toHaveClass('skeleton-card-wrapper');
  });

  it('renders header with badges', () => {
    const { container } = render(<SkeletonCard />);
    const header = container.querySelector('.skeleton-card-header');
    expect(header).toBeInTheDocument();
  });

  it('renders body with title and text', () => {
    const { container } = render(<SkeletonCard />);
    const body = container.querySelector('.skeleton-card-body');
    expect(body).toBeInTheDocument();
  });
});

describe('SkeletonRow', () => {
  it('renders row skeleton', () => {
    const { container } = render(<SkeletonRow />);
    const row = container.querySelector('.skeleton-row');
    expect(row).toBeInTheDocument();
    expect(row).toHaveClass('skeleton-row');
  });

  it('renders content and actions', () => {
    const { container } = render(<SkeletonRow />);
    const row = container.querySelector('.skeleton-row');
    expect(row.querySelector('.skeleton-row-content')).toBeInTheDocument();
    expect(row.querySelector('.skeleton-row-actions')).toBeInTheDocument();
  });
});

describe('SkeletonStatsCard', () => {
  it('renders stats card skeleton', () => {
    const { container } = render(<SkeletonStatsCard />);
    const card = container.querySelector('.skeleton-stats-card');
    expect(card).toBeInTheDocument();
    expect(card).toHaveClass('skeleton-stats-card');
  });

  it('renders value and label skeletons', () => {
    const { container } = render(<SkeletonStatsCard />);
    const card = container.querySelector('.skeleton-stats-card');
    expect(card.querySelector('.skeleton-stats-value')).toBeInTheDocument();
    expect(card.querySelector('.skeleton-stats-label')).toBeInTheDocument();
  });
});

describe('SkeletonProfile', () => {
  it('renders profile skeleton', () => {
    const { container } = render(<SkeletonProfile />);
    const profile = container.querySelector('.skeleton-profile');
    expect(profile).toBeInTheDocument();
    expect(profile).toHaveClass('skeleton-profile');
  });

  it('renders tags', () => {
    const { container } = render(<SkeletonProfile />);
    const tags = container.querySelector('.skeleton-profile-tags');
    expect(tags).toBeInTheDocument();
  });
});

describe('SkeletonList', () => {
  it('renders default count of rows', () => {
    const { container } = render(<SkeletonList />);
    const rows = container.querySelectorAll('.skeleton-row');
    expect(rows.length).toBeGreaterThanOrEqual(3);
  });

  it('renders specified count', () => {
    const { container } = render(<SkeletonList count={5} />);
    const rows = container.querySelectorAll('.skeleton-row');
    expect(rows.length).toBeGreaterThanOrEqual(5);
  });

  it('renders card type when specified', () => {
    const { container } = render(<SkeletonList type="card" count={2} />);
    const cards = container.querySelectorAll('.skeleton-card-wrapper');
    expect(cards.length).toBeGreaterThanOrEqual(2);
  });
});

describe('SkeletonProgressBar', () => {
  it('renders progress bar skeleton', () => {
    const { container } = render(<SkeletonProgressBar />);
    const progress = container.querySelector('.skeleton-progress');
    expect(progress).toBeInTheDocument();
    expect(progress).toHaveClass('skeleton-progress');
  });

  it('renders bar and text elements', () => {
    const { container } = render(<SkeletonProgressBar />);
    const progress = container.querySelector('.skeleton-progress');
    expect(progress.querySelector('.skeleton-progress-bar')).toBeInTheDocument();
    expect(progress.querySelector('.skeleton-progress-text')).toBeInTheDocument();
  });
});
