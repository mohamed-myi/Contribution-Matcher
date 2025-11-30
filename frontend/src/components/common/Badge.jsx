import './Badge.css';

export function Badge({
  children,
  variant = 'default',
  size = 'md',
  className = '',
  ...props
}) {
  const classes = [
    'badge',
    `badge-${variant}`,
    `badge-${size}`,
    className
  ].filter(Boolean).join(' ');

  return (
    <span className={classes} {...props}>
      {children}
    </span>
  );
}

export function DifficultyBadge({ difficulty, size = 'md' }) {
  const variant = {
    beginner: 'beginner',
    intermediate: 'intermediate',
    advanced: 'advanced',
    'good first issue': 'beginner',
  }[difficulty?.toLowerCase()] || 'default';

  return (
    <Badge variant={variant} size={size}>
      {difficulty || 'Unknown'}
    </Badge>
  );
}

export function ScoreBadge({ score, size = 'md' }) {
  let variant = 'default';
  if (score >= 80) variant = 'success';
  else if (score >= 60) variant = 'warning';
  else if (score >= 40) variant = 'info';
  else variant = 'muted';

  return (
    <Badge variant={variant} size={size}>
      {Math.round(score)}%
    </Badge>
  );
}

export function TechBadge({ tech, size = 'sm' }) {
  return (
    <Badge variant="tech" size={size}>
      {tech}
    </Badge>
  );
}

export default Badge;

