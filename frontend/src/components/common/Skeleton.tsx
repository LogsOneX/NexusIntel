export default function Skeleton({ rows = 3 }: { rows?: number }) {
  return <div className="skeleton-stack">{Array.from({ length: rows }).map((_, index) => <span key={index} />)}</div>;
}

