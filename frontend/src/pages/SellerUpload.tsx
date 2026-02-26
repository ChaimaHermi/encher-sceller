import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadImages } from '../api/client';

const CATEGORIES = ['antique', 'art', 'bijoux', 'mobilier', 'arts décoratifs', 'livres', 'autres'];

export function SellerUpload() {
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('');
  const [description, setDescription] = useState('');
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
      const { listing_id } = await uploadImages({
        files,
        title: title.trim() || undefined,
        category: category.trim() || undefined,
        description: description.trim() || undefined,
      });
      navigate(`/listing/${listing_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur lors de l'upload");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="upload-page">
      <h1>Nouveau produit</h1>
      <p className="upload-desc">
        Remplissez les informations et ajoutez une ou plusieurs photos.
      </p>
      <form onSubmit={handleSubmit} className="upload-form">
        <div className="form-fields">
          <label>
            <span>Titre</span>
            <input
              type="text"
              placeholder="Ex. Vase en porcelaine ancienne"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label>
            <span>Catégorie</span>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">— Choisir —</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Description courte</span>
            <textarea
              placeholder="Décrivez brièvement l'objet..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </label>
        </div>
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
              : 'Photos du produit — cliquez ou glissez une ou plusieurs images (JPEG, PNG, WEBP)'}
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
