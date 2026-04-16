import type { FeePrediction } from '../types/api';

interface FeeCardProps {
  title: string;
  prediction: FeePrediction | undefined;
  networkFee: number | undefined;
  priority: 'low' | 'medium' | 'high';
}

const priorityStyles = {
  low: {
    border: 'border-mempool-blue',
    text: 'text-mempool-blue',
    glow: 'shadow-[0_0_8px_#3d5afe]',
    barBg: 'bg-blue-900/20',
    barFill: 'bg-mempool-blue',
  },
  medium: {
    border: 'border-mempool-yellow',
    text: 'text-mempool-yellow',
    glow: 'shadow-[0_0_8px_#f5d41f]',
    barBg: 'bg-yellow-900/20',
    barFill: 'bg-mempool-yellow',
  },
  high: {
    border: 'border-mempool-orange',
    text: 'text-mempool-orange',
    glow: 'shadow-[0_0_8px_#f7931a]',
    barBg: 'bg-orange-900/20',
    barFill: 'bg-mempool-orange',
  },
};

export function FeeCard({ title, prediction, networkFee, priority }: FeeCardProps) {
  const styles = priorityStyles[priority];
  const predValue = prediction?.predicted_fee_sat_vb ?? '--';
  const netValue = networkFee ?? '--';
  const confidence = prediction ? Math.round(prediction.confidence_score * 100) : 0;

  return (
    <div className={`hud-border bg-black/60 p-4 flex-1 flex flex-col justify-between ${styles.border}`}>
      <div>
        <div className={`text-[10px] opacity-60 uppercase tracking-widest ${styles.text} font-bold`}>
          {title}
        </div>
        <div className="mt-4 space-y-3">
          <div className={`flex justify-between items-end border-b ${styles.border}/20 pb-1`}>
            <span className="text-[8px] opacity-60">ENSEMBLE_PRED</span>
            <div className="text-right">
              <span className={`text-2xl font-bold leading-none ${styles.text} ${priority === 'high' || priority === 'medium' ? `shadow-[0_0_8px_${priority === 'high' ? '#f7931a' : '#f5d41f'}]` : ''}`}>
                {predValue}
              </span>
              <span className="text-[8px] block opacity-80">sat/vB</span>
            </div>
          </div>
          
          <div className="flex justify-between items-end">
            <span className="text-[8px] opacity-60">NETWORK_FEE</span>
            <div className="text-right">
              <span className="text-2xl font-bold leading-none opacity-80">{netValue}</span>
              <span className="text-[8px] block opacity-80">sat/vB</span>
            </div>
          </div>
          
          {prediction && (
            <div className="flex justify-between items-end text-[8px]">
              <span className="opacity-60">XGB / LGB</span>
              <div className="text-right opacity-80">
                <span>{prediction.individual_predictions.xgb.toFixed(2)}</span>
                <span className="mx-1">/</span>
                <span>{prediction.individual_predictions.lgb.toFixed(2)}</span>
              </div>
            </div>
          )}
        </div>
      </div>
      
      <div className={`w-full ${styles.barBg} h-1 mt-4`}>
        <div 
          className={`${styles.barFill} h-full transition-all duration-500 ${styles.glow}`}
          style={{ width: `${confidence}%` }}
        />
      </div>
      <div className="text-[8px] opacity-60 text-right mt-1">CONFIDENCE: {confidence}%</div>
    </div>
  );
}
