# 🏺 Enchères Scellées

Plateforme d'enchères intelligente — IA + Blockchain + Smart Contracts

## Démarrage rapide

### Option 1 : Script automatique (Windows)
```bash
start.bat
```
Ouvre 2 fenêtres : backend (port 8000) et frontend (port 5173).

### Option 2 : Manuelle

**Terminal 1 — Backend** (obligatoire avant le frontend) :
```bash
cd "encher scellé"
python -m uvicorn backend_api.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend** :
```bash
cd "encher scellé/frontend"
npm install
npm run dev
```

### Accès
- **Frontend** : http://localhost:5173
- **API docs** : http://localhost:8000/docs

## ⚠️ Erreur 404 sur /api/auth/login ?

Le **backend doit être lancé en premier**. Le frontend envoie les requêtes vers `localhost:8000` via le proxy Vite. Si le backend n'est pas démarré, vous obtiendrez des 404.

1. Vérifier que le backend tourne : ouvrir http://localhost:8000/docs
2. Si la page ne s'ouvre pas → lancer le backend (voir ci-dessus)
