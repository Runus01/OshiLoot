import { BrowserRouter, Link, Route, Routes } from "react-router";
import { CountryDialog } from "./components/CountryDialog";
import { RegionProvider, useRegion } from "./context";
import { AnimePage } from "./pages/AnimePage";
import { CharacterRoute } from "./pages/CharacterPage";
import { Home } from "./pages/Home";
import { SongRoute } from "./pages/SongPage";

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
              <Route path="/anime/:id/character/:characterId" element={<CharacterRoute />} />
              <Route path="/anime/:id/song/:themeId" element={<SongRoute />} />
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
      <p>
        Anime and theme song data from MyAnimeList. Character data from AniList. Song previews courtesy of iTunes. Not
        affiliated with MyAnimeList, AniList, Apple or any store.
      </p>
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
