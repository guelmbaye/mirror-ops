"use client";

interface Option<T extends string> {
  value: T;
  label: string;
}

/**
 * Un groupe de choix, un seul sélectionné. Les boutons portent `aria-pressed`
 * plutôt qu'un `<input radio>` masqué : la cible tactile est le bouton lui-même.
 */
export function ChoiceGroup<T extends string>({
  legend,
  options,
  value,
  onChange,
  columns = 2,
}: {
  legend: string;
  options: readonly Option<T>[];
  value: T | null;
  onChange: (value: T) => void;
  columns?: number;
}) {
  return (
    <fieldset className="choice-set">
      <legend className="choice-set__legend">{legend}</legend>
      <div
        className="choice-grid"
        style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
      >
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            className="choice"
            aria-pressed={value === option.value}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
