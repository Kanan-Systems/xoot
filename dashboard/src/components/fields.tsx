// Labelled form controls shared by the write forms, with the schema's limits.
// Required fields are marked for assistive tech but checked by the forms, so
// every refusal shows the same inline message instead of a browser bubble.
import { useId, type Ref } from 'react';

import { LIMITS } from '../lib/limits.ts';

interface TextProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  inputRef?: Ref<HTMLInputElement>;
  required?: boolean;
}

export function TitleField({
  label,
  value,
  onChange,
  inputRef,
  required = true,
}: TextProps) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        ref={inputRef}
        type="text"
        value={value}
        aria-required={required}
        maxLength={LIMITS.titleMax}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
    </label>
  );
}

export function BodyField({
  label,
  value,
  onChange,
  required = false,
}: Omit<TextProps, 'inputRef'>) {
  return (
    <label className="field">
      <span>{label}</span>
      <textarea
        value={value}
        rows={6}
        aria-required={required}
        maxLength={LIMITS.bodyMax}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
    </label>
  );
}

interface Choice {
  value: string;
  label: string;
}

interface SelectProps {
  label: string;
  value: string;
  choices: readonly Choice[];
  onChange: (value: string) => void;
  // A first, empty choice, such as "Choose a batch".
  placeholder?: string;
}

export function SelectField({
  label,
  value,
  choices,
  onChange,
  placeholder,
}: SelectProps) {
  return (
    <label className="field">
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      >
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {choices.map((choice) => (
          <option key={choice.value} value={choice.value}>
            {choice.label}
          </option>
        ))}
      </select>
    </label>
  );
}

// A small set of exclusive options as radio buttons, compact enough for the
// drawer, where a native select's popup could overflow it.
export function ChoiceField({
  label,
  value,
  choices,
  onChange,
}: Omit<SelectProps, 'placeholder'>) {
  const name = useId();
  return (
    <fieldset className="field choice-field">
      <legend>{label}</legend>
      <div className="choices">
        {choices.map((choice) => (
          <label key={choice.value} className="choice">
            <input
              type="radio"
              name={name}
              value={choice.value}
              checked={value === choice.value}
              onChange={() => {
                onChange(choice.value);
              }}
            />{' '}
            {choice.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
