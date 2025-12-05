import './Skeleton.css';

/**
 * SkeletonText - Animated text placeholder with configurable lines
 */
export function SkeletonText({ lines = 1, width = '100%', className = '' }) {
  const textLines = Array.from({ length: lines });
  
  return (
    <div className={`skeleton-text-group ${className}`}>
      {textLines.map((_, index) => (
        <div
          key={index}
          className="skeleton skeleton-text-line"
          style={{
            width: index === lines - 1 && lines > 1 ? '80%' : width,
          }}
        />
      ))}
    </div>
  );
}

/**
 * SkeletonBadge - Small badge placeholder
 */
export function SkeletonBadge({ width = '60px', className = '' }) {
  return (
    <div
      className={`skeleton skeleton-badge ${className}`}
      style={{ width }}
    />
  );
}

/**
 * SkeletonCard - Issue card skeleton with header, body, badges
 */
export function SkeletonCard({ className = '' }) {
  return (
    <div className={`skeleton-card-wrapper ${className}`}>
      <div className="skeleton-card-header">
        <div className="skeleton-card-badges">
          <SkeletonBadge width="70px" />
          <SkeletonBadge width="50px" />
        </div>
        <SkeletonBadge width="90px" />
      </div>
      
      <div className="skeleton-card-body">
        <div className="skeleton skeleton-card-title" />
        <div className="skeleton skeleton-card-repo" />
        <SkeletonText lines={3} />
        
        <div className="skeleton-card-techs">
          <SkeletonBadge width="60px" />
          <SkeletonBadge width="75px" />
          <SkeletonBadge width="55px" />
          <SkeletonBadge width="70px" />
        </div>
      </div>
    </div>
  );
}

/**
 * SkeletonRow - Table/list row skeleton
 */
export function SkeletonRow({ className = '' }) {
  return (
    <div className={`skeleton-row ${className}`}>
      <div className="skeleton-row-content">
        <div className="skeleton skeleton-row-title" />
        <div className="skeleton skeleton-row-subtitle" />
      </div>
      <div className="skeleton-row-actions">
        <SkeletonBadge width="60px" />
        <SkeletonBadge width="50px" />
      </div>
    </div>
  );
}

/**
 * SkeletonStatsCard - Stats card skeleton for dashboard
 */
export function SkeletonStatsCard({ className = '' }) {
  return (
    <div className={`skeleton-stats-card ${className}`}>
      <div className="skeleton skeleton-stats-value" />
      <div className="skeleton skeleton-stats-label" />
    </div>
  );
}

/**
 * SkeletonProfile - Profile card section skeleton
 */
export function SkeletonProfile({ className = '' }) {
  return (
    <div className={`skeleton-profile ${className}`}>
      <div className="skeleton skeleton-profile-header" />
      <div className="skeleton-profile-tags">
        <SkeletonBadge width="70px" />
        <SkeletonBadge width="90px" />
        <SkeletonBadge width="65px" />
        <SkeletonBadge width="80px" />
        <SkeletonBadge width="60px" />
      </div>
    </div>
  );
}

/**
 * SkeletonList - Multiple skeleton rows/items
 */
export function SkeletonList({ count = 3, type = 'row', className = '' }) {
  const items = Array.from({ length: count });
  
  return (
    <div className={`skeleton-list ${className}`}>
      {items.map((_, index) => {
        if (type === 'card') {
          return <SkeletonCard key={index} />;
        }
        return <SkeletonRow key={index} />;
      })}
    </div>
  );
}

/**
 * SkeletonProgressBar - Progress bar skeleton
 */
export function SkeletonProgressBar({ className = '' }) {
  return (
    <div className={`skeleton-progress ${className}`}>
      <div className="skeleton skeleton-progress-bar" />
      <div className="skeleton-progress-text">
        <div className="skeleton skeleton-progress-label" />
        <div className="skeleton skeleton-progress-value" />
      </div>
    </div>
  );
}

export default SkeletonCard;

