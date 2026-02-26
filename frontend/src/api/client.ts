import { authFetch } from '../context/AuthContext';

export async function uploadImage(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  const token = localStorage.getItem('encher_token');
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch('/api/upload', {
    method: 'POST',
    headers,
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Upload échoué');
  }
  return res.json();
}

export async function getListing(listingId: string) {
  const res = await authFetch(`/api/listing/${listingId}`);
  if (!res.ok) throw new Error('Listing introuvable');
  return res.json();
}

export async function getListings() {
  const res = await authFetch('/api/listings/');
  if (!res.ok) throw new Error('Erreur chargement');
  return res.json();
}

export async function runPipelineStep(listingId: string, step: 'analyze' | 'estimate' | 'generate' | 'deploy') {
  const res = await authFetch(`/api/listing/${listingId}/${step}`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Erreur');
  }
  return res.json();
}

export async function placeBid(listingId: string, amount: number) {
  const res = await authFetch(`/api/listing/${listingId}/bid`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Erreur');
  }
  return res.json();
}
