export default function GlassCard({ children, className = "", ...props }) {
  return (
    <div className={`glass-panel p-6 animate-fade-in ${className}`} {...props}>
      {children}
    </div>
  );
}
