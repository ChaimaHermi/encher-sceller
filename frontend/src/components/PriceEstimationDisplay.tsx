interface PriceEstimationDisplayProps {
  data: Record<string, unknown>;
}

export function PriceEstimationDisplay({ data }: PriceEstimationDisplayProps) {
  const low = typeof data.low === 'number' ? data.low : null;
  const median = typeof data.median === 'number' ? data.median : null;
  const high = typeof data.high === 'number' ? data.high : null;
  const starting = typeof data.starting_price === 'number' ? data.starting_price : median;
  const reasoning = data.reasoning != null ? String(data.reasoning) : '';

  const formatPrice = (n: number) => `${n.toFixed(0)} €`;

  return (
    <div className="price-estimation-display">
      <div className="price-cards">
        {low != null && (
          <div className="price-card price-low">
            <span className="price-label">Minimum</span>
            <span className="price-value">{formatPrice(low)}</span>
          </div>
        )}
        {median != null && (
          <div className="price-card price-median">
            <span className="price-label">Médian suggéré</span>
            <span className="price-value">{formatPrice(median)}</span>
          </div>
        )}
        {high != null && (
          <div className="price-card price-high">
            <span className="price-label">Maximum</span>
            <span className="price-value">{formatPrice(high)}</span>
          </div>
        )}
      </div>
      {starting != null && starting !== median && (
        <div className="price-starting">
          <strong>Prix de départ recommandé :</strong> {formatPrice(starting)}
        </div>
      )}
      {reasoning && (
        <div className="price-reasoning">
          <h4>Raisonnement</h4>
          <div className="price-reasoning-text">{reasoning}</div>
        </div>
      )}
    </div>
  );
}
