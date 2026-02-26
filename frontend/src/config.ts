/** URL de base de l'API — évite les 404 quand le port frontend change (5173/5174) */
export const API_BASE =
  import.meta.env.DEV ? 'http://localhost:8000' : '';
