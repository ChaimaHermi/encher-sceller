import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadImage } from '../api/client';

export function SellerUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setError('Veuillez sélectionner une image');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { listing_id } = await uploadImage(file);
      navigate(`/listing/${listing_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur lors de l'upload");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="upload-page">
      <h1>📤 Étape 1 — Upload du produit</h1>
      <p>
        Déposez une photo haute résolution de votre objet. Format JPEG, PNG ou WEBP. Min. 1000×1000 px.
      </p>
      <form onSubmit={handleSubmit} className="upload-form">
        <label className="upload-zone">
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          {file ? (
            <span>📷 {file.name}</span>
          ) : (
            <span>Cliquez ou glissez une image ici</span>
          )}
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={loading} className="cta">
          {loading ? 'Upload en cours…' : 'Envoyer'}
        </button>
      </form>
    </section>
  );
}
