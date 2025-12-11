import { Link } from 'react-router-dom';
import { createPreloadHandlers } from '../../utils/routePreloader';

/**
 * PreloadLink - Enhanced Link component that preloads routes on hover/focus
 * Drop-in replacement for react-router-dom Link with automatic preloading
 */
export function PreloadLink({ to, preload, children, className, ...props }) {
  // Only add preload handlers if preload prop is provided
  const preloadHandlers = preload ? createPreloadHandlers(preload) : {};
  
  return (
    <Link 
      to={to} 
      className={className}
      {...preloadHandlers}
      {...props}
    >
      {children}
    </Link>
  );
}

export default PreloadLink;

