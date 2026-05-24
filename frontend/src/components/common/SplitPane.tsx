export default function SplitPane({ left, right, children }: { left?: React.ReactNode; right?: React.ReactNode; children: React.ReactNode }) {
  return <div className="split-pane">{left && <aside>{left}</aside>}<main>{children}</main>{right && <aside>{right}</aside>}</div>;
}

