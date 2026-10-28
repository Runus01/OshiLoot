import { BrowserRouter, Link, Route, Routes } from "react-router";
import { CountryDialog } from "./components/CountryDialog";
import { RegionProvider, useRegion } from "./context";
import { AnimePage } from "./pages/AnimePage";
import { Home } from "./pages/Home";

export function App() {
  return (
    <RegionProvider>
      <BrowserRouter>
        <div className="page">
          <Header />
          <main className="main">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/anime/:id" element={<AnimePage />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </main>
          <Footer />
        </div>
        <CountryDialog />
      </BrowserRouter>
    </RegionProvider>
  );
}

function Header() {
  const { country, openPicker } = useRegion();
  return (
    <header className="header">
      <Link to="/" className="wordmark">
        OshiLoot
      </Link>
      <button type="button" className="country-button" onClick={openPicker}>
        {country ? `Shipping to ${country.name}` : "Choose your country"}
      </button>
    </header>
  );
}

function Footer() {
  return (
    <footer className="footer">
      <p>
        Some store links are affiliate links: if you buy through them, this site may earn a
        commission at no extra cost to you. Prices and shipping change often, so check the
        store before you pay.
      </p>
      <p>Anime data from MyAnimeList. Not affiliated with MyAnimeList or any store.</p>
    </footer>
  );
}

function NotFound() {
  return (
    <section className="empty">
      <h1>That page doesn't exist.</h1>
      <Link to="/">Go to your list</Link>
    </section>
  );
}
