// One URL filter of a view: a labelled select whose first option, "All",
// clears it. Shared by the Decisions and Backlog tabs.
interface FilterProps {
  label: string;
  value: string | null;
  options: readonly { value: string; label: string }[];
  onChange: (value: string | null) => void;
}

export function Filter({ label, value, options, onChange }: FilterProps) {
  return (
    <label className="control">
      {label}{' '}
      <select
        value={value ?? ''}
        onChange={(event) => {
          onChange(event.target.value === '' ? null : event.target.value);
        }}
      >
        <option value="">All</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
