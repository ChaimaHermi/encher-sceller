import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getListing, runPipelineStep, placeBid } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { PipelineStepper } from '../components/PipelineStepper';

interface Listing {
  listing_id: string;
  seller_id?: string;
  image: { filename: string; original_name: string };
  title?: string;
  starting_price?: number;
  participants_count?: number;
  end_time?: string;
  status: string;
  pipeline_phase?: number;
  ai_analysis?: Record<string, unknown>;
  price_estimation?: Record<string, unknown>;
  generated_post?: Record<string, unknown>;
  blockchain?: { auction_address?: string };
}

const NEXT_STEP: Record<number, { label: string; step: 'analyze' | 'estimate' | 'generate' | 'deploy' }> = {
  1: { label: 'Lancer vérification authenticité (IA)', step: 'analyze' },
  2: { label: 'Lancer estimation prix (IA)', step: 'estimate' },
  3: { label: 'Générer le post (IA)', step: 'generate' },
  4: { label: 'Déployer sur blockchain', step: 'deploy' },
};

export function ListingDetail() {
  const { listingId } = useParams<{ listingId: string }>();
  const { user } = useAuth();
  const [listing, setListing] = useState<Listing | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [bidAmount, setBidAmount] = useState('');
  const [bidSuccess, setBidSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isSeller = user?.role === 'seller';
  const isBuyer = user?.role === 'buyer';

  function refresh() {
    if (!listingId) return;
    getListing(listingId)
      .then(setListing)
      .catch(() => setError('Erreur'))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!listingId) return;
    setLoading(true);
    getListing(listingId).then(setListing).catch(() => setError('Erreur')).finally(() => setLoading(false));
  }, [listingId]);

  async function handlePipelineStep() {
    if (!listingId || !listing) return;
    const next = NEXT_STEP[listing.pipeline_phase!];
    if (!next) return;
    setActionLoading(true);
    setError(null);
    try {
      await runPipelineStep(listingId, next.step);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur');
    } finally {
      setActionLoading(false);
    }
  }

  async function handleBid(e: React.FormEvent) {
    e.preventDefault();
    if (!listingId || !bidAmount) return;
    const amount = parseFloat(bidAmount.replace(',', '.'));
    if (isNaN(amount) || amount <= 0) {
      setError('Montant invalide');
      return;
    }
    const min = listing?.starting_price ?? 0;
    if (amount < min) {
      setError(`Le montant minimum est ${min} €`);
      return;
    }
    setActionLoading(true);
    setError(null);
    setBidSuccess(false);
    try {
      await placeBid(listingId, amount);
      setBidSuccess(true);
      setBidAmount('');
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur');
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) return <div className="loading-screen"><div className="spinner" /></div>;
  if (error && !listing) return <p className="error">Erreur : {error}</p>;
  if (!listing) return null;

  const imageUrl = `/uploads/${listing.image.filename}`;
  const canAdvance = isSeller && listing.pipeline_phase != null && listing.pipeline_phase < 5 && NEXT_STEP[listing.pipeline_phase];
  const isAuctionActive = listing.status === 'AUCTION_ACTIVE';

  return (
    <section className="listing-detail">
      <div className="listing-header">
        <h1>{listing.title || `Listing ${listing.listing_id.slice(0, 8)}…`}</h1>
        {isSeller && <Link to="/seller/dashboard" className="back-link">← Retour</Link>}
        {isBuyer && <Link to="/buyer/catalog" className="back-link">← Retour aux enchères</Link>}
      </div>

      {/* Pipeline visible uniquement pour le vendeur */}
      {isSeller && listing.pipeline_phase != null && (
        <PipelineStepper currentPhase={listing.pipeline_phase} />
      )}

      <div className="listing-content">
        <div className="listing-image">
          <img src={imageUrl} alt={listing.image.original_name} />
        </div>
        <div className="listing-info">
          <p><strong>Statut :</strong> {listing.status}</p>
          {isSeller && listing.pipeline_phase != null && (
            <p><strong>Phase :</strong> {listing.pipeline_phase} / 6</p>
          )}
          {listing.starting_price != null && (
            <p><strong>Prix de départ :</strong> {listing.starting_price} €</p>
          )}
          {listing.participants_count != null && (
            <p><strong>Participants :</strong> {listing.participants_count}</p>
          )}
          {listing.end_time && (
            <p><strong>Fin :</strong> {new Date(listing.end_time).toLocaleString('fr-FR')}</p>
          )}

          {/* Acheteur : formulaire d'enchère — pas de pipeline */}
          {isBuyer && isAuctionActive && (
            <div className="bid-form">
              <h3>Proposer un prix</h3>
              <p>Votre offre reste secrète jusqu'à la clôture. Vous ne voyez pas les offres des autres.</p>
              <form onSubmit={handleBid}>
                <div className="bid-input-group">
                  <input
                    type="number"
                    step="0.01"
                    min={listing.starting_price ?? 0}
                    placeholder="Montant (€)"
                    value={bidAmount}
                    onChange={(e) => setBidAmount(e.target.value)}
                  />
                  <button type="submit" className="cta" disabled={actionLoading}>
                    {actionLoading ? 'Envoi…' : 'Enchérir'}
                  </button>
                </div>
                {bidSuccess && <p className="bid-success">✓ Offre enregistrée (scellée)</p>}
                {error && <p className="error">{error}</p>}
              </form>
            </div>
          )}

          {/* Vendeur : infos pipeline + boutons */}
          {isSeller && listing.ai_analysis && (
            <details>
              <summary>Analyse IA (authenticité)</summary>
              <pre>{JSON.stringify(listing.ai_analysis, null, 2)}</pre>
            </details>
          )}
          {isSeller && listing.price_estimation && (
            <details>
              <summary>Estimation prix</summary>
              <pre>{JSON.stringify(listing.price_estimation, null, 2)}</pre>
            </details>
          )}
          {isSeller && canAdvance && (
            <button
              className="cta pipeline-btn"
              onClick={handlePipelineStep}
              disabled={actionLoading}
            >
              {actionLoading ? 'En cours…' : NEXT_STEP[listing.pipeline_phase!].label}
            </button>
          )}
          {isSeller && listing.blockchain?.auction_address && (
            <Link to={`/auction/${listing.blockchain.auction_address}`} className="cta">
              Voir l'enchère
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
