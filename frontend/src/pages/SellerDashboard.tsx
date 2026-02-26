import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getListings } from '../api/client';
import { PipelineStepper } from '../components/PipelineStepper';

interface Listing {
  listing_id: string;
  image: { filename: string; original_name: string };
  title?: string;
  starting_price?: number;
  status: string;
  pipeline_phase: number;
}

const STEP_LABELS: Record<number, string> = {
  1: 'Upload',
  2: 'Authenticité',
  3: 'Prix',
  4: 'Post',
  5: 'Smart Contract',
  6: 'Enchère',
};

export function SellerDashboard() {
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
    <section className="seller-dashboard">
      <div className="dashboard-header">
        <h1>🏪 Mes ventes</h1>
        <Link to="/seller/upload" className="cta">+ Nouveau produit</Link>
      </div>
      <p className="pipeline-info">
        Pipeline : <strong>Upload</strong> → <strong>Authenticité (IA)</strong> → <strong>Prix (IA)</strong> → <strong>Post (IA)</strong> → <strong>Blockchain</strong> → <strong>Enchère</strong>
      </p>
      <div className="seller-listings">
        {listings.length === 0 ? (
          <div className="empty-state">
            <p>Aucun produit. Déposez une photo pour lancer une enchère.</p>
            <Link to="/seller/upload" className="cta">Déposer un produit</Link>
          </div>
        ) : (
          listings.map((l) => (
            <div key={l.listing_id} className="seller-card">
              <div className="seller-card-image">
                <img src={`/uploads/${l.image.filename}`} alt={l.image.original_name} />
              </div>
              <div className="seller-card-body">
                <h3>{l.title || 'Sans titre'}</h3>
                <PipelineStepper currentPhase={l.pipeline_phase} />
                <p className="status">Phase actuelle : {STEP_LABELS[l.pipeline_phase]}</p>
                <Link to={`/listing/${l.listing_id}`} className="btn-link">Voir / Continuer</Link>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
