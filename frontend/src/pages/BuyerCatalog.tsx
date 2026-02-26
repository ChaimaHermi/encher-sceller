import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getListings } from '../api/client';

interface Listing {
  listing_id: string;
  image: { filename: string; original_name: string };
  title?: string;
  starting_price?: number;
  participants_count: number;
  end_time?: string;
  status: string;
}

export function BuyerCatalog() {
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getListings()
      .then(setListings)
      .catch(() => setListings([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading-screen"><div className="spinner" /></div>;

  return (
    <section className="catalog-page">
      <h1>🛒 Enchères en cours</h1>
      <p className="catalog-desc">
        Vous voyez le prix de départ et le nombre de participants.
        <strong> Les offres des autres enchérisseurs restent secrètes</strong> — c'est l'enchère scellée.
      </p>
      <div className="listing-cards">
        {listings.length === 0 ? (
          <p className="empty">Aucune enchère pour le moment.</p>
        ) : (
          listings.map((l) => (
            <Link key={l.listing_id} to={`/listing/${l.listing_id}`} className="listing-card">
              <div className="card-image">
                <img src={`/uploads/${l.image.filename}`} alt={l.image.original_name} />
              </div>
              <div className="card-body">
                <h3>{l.title || 'Sans titre'}</h3>
                <div className="card-meta">
                  <span className="price">Prix de départ : <strong>{l.starting_price ?? '—'} €</strong></span>
                  <span className="participants">👥 {l.participants_count} participant(s)</span>
                </div>
                {l.end_time && (
                  <p className="end-time">Fin : {new Date(l.end_time).toLocaleDateString('fr-FR')}</p>
                )}
              </div>
            </Link>
          ))
        )}
      </div>
    </section>
  );
}
