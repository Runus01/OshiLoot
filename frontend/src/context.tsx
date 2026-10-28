import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
import { countryFromLocale, saveCountry, savedCountry } from "./lib/storage";
import type { Country, FxRates } from "./types";

interface Region {
  countries: Country[];
  country: Country | null; // null until the user has picked one
  suggested: string | null;
  setCountry: (code: string) => void;
  fx: FxRates | null;
  pickerOpen: boolean;
  openPicker: () => void;
  closePicker: () => void;
}

const RegionContext = createContext<Region | null>(null);

export function RegionProvider({ children }: { children: ReactNode }) {
  const [countries, setCountries] = useState<Country[]>([]);
  const [code, setCode] = useState<string | null>(savedCountry());
  const [suggested, setSuggested] = useState<string | null>(null);
  const [fx, setFx] = useState<FxRates | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    api
      .countries()
      .then((res) => {
        setCountries(res.countries);
        const guess = res.detected ?? countryFromLocale(navigator.language);
        setSuggested(res.countries.some((c) => c.code === guess) ? guess : "US");
      })
      .catch(() => setCountries([]));
    // Prices still show in their original currency if rates are unavailable.
    api.fx().then(setFx).catch(() => setFx(null));
  }, []);

  const value = useMemo<Region>(() => {
    const country = countries.find((c) => c.code === code) ?? null;
    return {
      countries,
      country,
      suggested,
      fx,
      setCountry: (next) => {
        saveCountry(next);
        setCode(next);
        setPickerOpen(false);
      },
      pickerOpen: pickerOpen || (countries.length > 0 && country === null),
      openPicker: () => setPickerOpen(true),
      closePicker: () => setPickerOpen(false),
    };
  }, [countries, code, suggested, fx, pickerOpen]);

  return <RegionContext.Provider value={value}>{children}</RegionContext.Provider>;
}

export function useRegion(): Region {
  const region = useContext(RegionContext);
  if (!region) throw new Error("useRegion must be used inside RegionProvider");
  return region;
}
