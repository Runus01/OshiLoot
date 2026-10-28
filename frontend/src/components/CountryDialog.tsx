import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRegion } from "../context";

/** Native <dialog>: focus trapping and Escape handling come from the browser. */
export function CountryDialog() {
  const { countries, country, suggested, setCountry, pickerOpen, closePicker } = useRegion();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [choice, setChoice] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (pickerOpen && !dialog.open) {
      setChoice(country?.code ?? suggested);
      dialog.showModal();
    } else if (!pickerOpen && dialog.open) {
      dialog.close();
    }
  }, [pickerOpen, country, suggested]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (choice) setCountry(choice);
  };

  return (
    <dialog
      ref={dialogRef}
      className="country-dialog"
      aria-labelledby="country-title"
      onCancel={(event) => {
        // A first-time visitor has to pick before the merch pages make sense.
        if (!country) event.preventDefault();
        else closePicker();
      }}
    >
      <form onSubmit={submit}>
        <h2 id="country-title">Where should merch ship to?</h2>
        <p className="muted">
          This decides which stores you see, the currency prices are shown in, and the shipping
          we quote. You can change it any time.
        </p>
        <fieldset className="country-grid">
          <legend className="visually-hidden">Country</legend>
          {countries.map((c) => (
            <label key={c.code} className="country-option">
              <input
                type="radio"
                name="country"
                value={c.code}
                checked={choice === c.code}
                onChange={() => setChoice(c.code)}
              />
              <span>{c.name}</span>
              <span className="muted">{c.currency}</span>
            </label>
          ))}
        </fieldset>
        <div className="dialog-actions">
          {country && (
            <button type="button" className="button-quiet" onClick={closePicker}>
              Cancel
            </button>
          )}
          <button type="submit" className="button" disabled={!choice}>
            Save country
          </button>
        </div>
      </form>
    </dialog>
  );
}
