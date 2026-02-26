interface AnalysisOutputProps {
  data: Record<string, unknown>;
}

const VERDICT_LABELS: Record<string, string> = {
  validated: 'Validé',
  duplicate: 'Doublon détecté',
  duplicate_or_manipulated: 'Doublon ou manipulé',
  ai_generated: 'Généré par IA',
};

export function AnalysisOutput({ data }: AnalysisOutputProps) {
  const verdict = (data.verdict as string) || 'inconnu';
  const verdictLabel = VERDICT_LABELS[verdict] || verdict;
  const details = data.details as Record<string, unknown> | undefined;

  return (
    <div className="analysis-output">
      <div className={`verdict-badge verdict-${verdict.replace(/_/g, '-')}`}>
        {verdictLabel}
      </div>

      {data.authenticity_reasoning && (
        <div className="analysis-section">
          <h4>Raisonnement authenticité</h4>
          <div className="reasoning-text">{String(data.authenticity_reasoning)}</div>
        </div>
      )}

      {details && (
        <details className="analysis-details">
          <summary>Détails techniques</summary>
          <div className="details-grid">
            {details.ela && (
              <div className="detail-block">
                <strong>ELA</strong>
                <pre>{JSON.stringify(details.ela, null, 2)}</pre>
              </div>
            )}
            {details.reverse_search && (
              <div className="detail-block">
                <strong>Recherche inversée</strong>
                <pre>{JSON.stringify(details.reverse_search, null, 2)}</pre>
              </div>
            )}
            {details.ai_detection && (
              <div className="detail-block">
                <strong>Détection IA</strong>
                <pre>{JSON.stringify(details.ai_detection, null, 2)}</pre>
              </div>
            )}
            {details.vision_analysis && (
              <div className="detail-block">
                <strong>Analyse visuelle</strong>
                <pre>{JSON.stringify(details.vision_analysis, null, 2)}</pre>
              </div>
            )}
            {details.exif && (
              <div className="detail-block">
                <strong>EXIF</strong>
                <pre>{JSON.stringify(details.exif, null, 2)}</pre>
              </div>
            )}
            {details.comparative_search && (
              <div className="detail-block">
                <strong>Recherche comparative</strong>
                <pre>{JSON.stringify(details.comparative_search, null, 2)}</pre>
              </div>
            )}
          </div>
        </details>
      )}

      {verdict === 'duplicate' && details?.matched_filename && (
        <p className="duplicate-info">
          Fichier similaire : {String(details.matched_filename)}
        </p>
      )}
    </div>
  );
}
