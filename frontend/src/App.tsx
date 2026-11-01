import { useEffect } from "react";
import { BrowserRouter, Link, Route, Routes, useLocation, useNavigationType } from "react-router";
import logo from "./assets/logo.svg";
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
        <ScrollToTop />
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

/**
 * Opening a link (an anime, a character, a song) starts at the top of the new page. The
 * browser's back and forward buttons are left alone, so they return to where you were.
 */
function ScrollToTop() {
  const { pathname } = useLocation();
  const navigation = useNavigationType();
  useEffect(() => {
    if (navigation !== "POP") window.scrollTo(0, 0);
  }, [pathname, navigation]);
  return null;
}

function Header() {
  const { country, openPicker } = useRegion();
  return (
    <header className="header">
      <Link to="/" className="wordmark">
        <img src={logo} alt="" className="logo-mark" width={44} height={44} />
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
      {import.meta.env.VITE_CF_ANALYTICS_TOKEN && (
        <p>Visits are counted with Cloudflare Web Analytics, which uses no cookies and doesn't track individual visitors.</p>
      )}
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
