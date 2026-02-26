import { authFetch } from '../context/AuthContext';
import { API_BASE } from '../config';

export interface UploadListingParams {
  files: File[];
  title?: string;
  category?: string;
  description?: string;
}

export async function uploadImages({ files, title, category, description }: UploadListingParams) {
  const formData = new FormData();
  if (title) formData.append('title', title);
  if (category) formData.append('category', category);
  if (description) formData.append('description', description);
  files.forEach((f) => formData.append('files', f));
  const token = localStorage.getItem('encher_token');
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/api/upload`, {
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
  const controller = new AbortController();
  const timeout = step === 'analyze' ? 180000 : 30000;
  const id = setTimeout(() => controller.abort(), timeout);
  const res = await authFetch(`/api/listing/${listingId}/${step}`, {
    method: 'POST',
    signal: controller.signal,
  });
  clearTimeout(id);
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
