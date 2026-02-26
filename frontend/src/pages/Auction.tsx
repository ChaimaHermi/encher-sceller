import { useParams } from 'react-router-dom';

export function Auction() {
  const { address } = useParams<{ address: string }>();

  return (
    <section className="auction-page">
      <h1>Enchère</h1>
      <p>Adresse du contrat : <code>{address}</code></p>
      <p className="placeholder">
        Intégration Web3 à venir — affichage des offres, timer, soumission d'enchères.
      </p>
    </section>
  );
}
