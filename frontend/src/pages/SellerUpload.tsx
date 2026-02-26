import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadImages } from '../api/client';

export function SellerUpload() {
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    const valid = selected.filter((f) => f.type.startsWith('image/'));
    setFiles(valid);
    if (valid.length === 0) {
      setPreviews([]);
      return;
    }
    Promise.all(
      valid.map((f) => new Promise<string>((res) => {
        const r = new FileReader();
        r.onload = () => res(r.result as string);
        r.readAsDataURL(f);
      }))
    ).then(setPreviews);
  }, []);

  const removeFile = (i: number) => {
    setFiles((f) => f.filter((_, idx) => idx !== i));
    setPreviews((p) => p.filter((_, idx) => idx !== i));
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0) {
      setError('Sélectionnez au moins une image');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { listing_id } = await uploadImages(files);
      navigate(`/listing/${listing_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur lors de l'upload");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="upload-page">
      <h1>Étape 1 — Photos du produit</h1>
      <p className="upload-desc">
        Ajoutez une ou plusieurs photos (recto, verso, détails). Formats JPEG, PNG ou WEBP. Min. 1000×1000 px recommandé.
      </p>
      <form onSubmit={handleSubmit} className="upload-form">
        <label className="upload-zone">
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            onChange={handleFileChange}
          />
          <span className="upload-zone-text">
            {files.length > 0
              ? `${files.length} image(s) sélectionnée(s)`
              : 'Cliquez ou glissez une ou plusieurs images ici'}
          </span>
        </label>
        {previews.length > 0 && (
          <div className="upload-previews">
            {previews.map((src, i) => (
              <div key={i} className="upload-preview-item">
                <img src={src} alt={`Aperçu ${i + 1}`} />
                <button type="button" className="upload-remove" onClick={() => removeFile(i)} aria-label="Retirer">
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={loading || files.length === 0} className="cta">
          {loading ? 'Envoi en cours…' : 'Créer l\'annonce'}
        </button>
      </form>
    </section>
  );
}
