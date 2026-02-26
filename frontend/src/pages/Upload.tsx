import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadImage } from '../api/client';

export function Upload() {
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
      const msg = err instanceof Error ? err.message : "Erreur lors de l'upload";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="upload-page">
      <h1>Phase 1 — Upload &amp; Analyse</h1>
      <p>
        Téléchargez une photo haute résolution. Format JPEG, PNG ou WEBP. Résolution minimale 1000×1000 px.
      </p>
      <form onSubmit={handleSubmit} className="upload-form">
        <label>
          <span>Image du produit</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        {file && <p className="file-name">📷 {file.name}</p>}
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? 'Upload en cours…' : 'Envoyer'}
        </button>
      </form>
    </section>
  );
}
