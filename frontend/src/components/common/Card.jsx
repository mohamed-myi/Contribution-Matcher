import './Card.css';

export function Card({
  children,
  variant = 'default',
  padding = 'md',
  hover = false,
  glow = false,
  className = '',
  onClick,
  ...props
}) {
  const classes = [
    'card',
    `card-${variant}`,
    `card-padding-${padding}`,
    hover && 'card-hover',
    glow && 'card-glow',
    onClick && 'card-clickable',
    className
  ].filter(Boolean).join(' ');

  return (
    <div 
      className={classes} 
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className = '' }) {
  return (
    <div className={`card-header ${className}`}>
      {children}
    </div>
  );
}

export function CardBody({ children, className = '' }) {
  return (
    <div className={`card-body ${className}`}>
      {children}
    </div>
  );
}

export function CardFooter({ children, className = '' }) {
  return (
    <div className={`card-footer ${className}`}>
      {children}
    </div>
  );
}

export default Card;

