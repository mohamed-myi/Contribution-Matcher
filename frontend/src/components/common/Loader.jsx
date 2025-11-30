import './Loader.css';

export function Loader({ size = 'md', className = '' }) {
  const classes = ['loader', `loader-${size}`, className].filter(Boolean).join(' ');
  
  return (
    <div className={classes} role="status" aria-label="Loading">
      <div className="loader-spinner">
        <svg viewBox="0 0 50 50">
          <circle
            className="loader-track"
            cx="25"
            cy="25"
            r="20"
            fill="none"
            strokeWidth="4"
          />
          <circle
            className="loader-progress"
            cx="25"
            cy="25"
            r="20"
            fill="none"
            strokeWidth="4"
            strokeLinecap="round"
          />
        </svg>
      </div>
    </div>
  );
}

export function PageLoader({ message = 'Loading...' }) {
  return (
    <div className="page-loader">
      <Loader size="lg" />
      <p className="page-loader-message">{message}</p>
    </div>
  );
}

export function SkeletonLoader({ width, height, variant = 'text', className = '' }) {
  const classes = [
    'skeleton',
    `skeleton-${variant}`,
    className
  ].filter(Boolean).join(' ');

  const style = {
    width: width || (variant === 'text' ? '100%' : undefined),
    height: height || (variant === 'text' ? '1em' : undefined),
  };

  return <div className={classes} style={style} />;
}

export default Loader;

