import { Header } from './Header';
import './Layout.css';

export function Layout({ children }) {
  return (
    <div className="layout">
      {/* Flowing Sand Texture Background */}
      <div className="sand-texture" aria-hidden="true"></div>
      
      {/* Desert Abstract Lines Background */}
      <div className="desert-lines" aria-hidden="true">
        <div className="dune-arc dune-arc-1"></div>
        <div className="dune-arc dune-arc-2"></div>
        <div className="dune-arc dune-arc-3"></div>
        <div className="dune-arc dune-arc-4"></div>
        <div className="dune-arc dune-arc-5"></div>
      </div>

      <Header />
      
      <main className="layout-main">
        <div className="layout-container">
          {children}
        </div>
      </main>
    </div>
  );
}

export function AuthLayout({ children }) {
  return (
    <div className="auth-layout">
      {/* Flowing Sand Texture Background */}
      <div className="sand-texture" aria-hidden="true"></div>
      
      {/* Desert Abstract Lines Background */}
      <div className="desert-lines" aria-hidden="true">
        <div className="dune-arc dune-arc-1"></div>
        <div className="dune-arc dune-arc-2"></div>
        <div className="dune-arc dune-arc-3"></div>
        <div className="dune-arc dune-arc-4"></div>
        <div className="dune-arc dune-arc-5"></div>
      </div>

      <main className="auth-layout-main">
        {children}
      </main>
    </div>
  );
}

export default Layout;
