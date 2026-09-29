// The polling indicator: when /changes last answered, or that it fails.
interface LastUpdatedProps {
  checkedAt: number;
  failing: boolean;
}

export function LastUpdated({ checkedAt, failing }: LastUpdatedProps) {
  if (failing) {
    return (
      <p className="last-updated warning" role="status">
        ⚠ Live updates failing; showing the last data received.
      </p>
    );
  }
  const text =
    checkedAt === 0
      ? 'Connecting…'
      : `Last checked ${new Date(checkedAt).toLocaleTimeString()}`;
  return (
    <p className="last-updated" role="status">
      {text}
    </p>
  );
}
