import { useRef, useEffect } from 'react';
import type { FeePrediction } from '../types/api';

interface HexStreamProps {
  predictions: FeePrediction[];
  blockHash?: string;
}

export function HexStream({ predictions, blockHash }: HexStreamProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [predictions]);

  const generateHexRow = (index: number, prediction?: FeePrediction) => {
    const addr = `0x${(index * 16).toString(16).toUpperCase().padStart(4, '0')}`;
    
    if (prediction) {
      const xgb = prediction.individual_predictions.xgb.toFixed(2);
      const lgb = prediction.individual_predictions.lgb.toFixed(2);
      const ensemble = prediction.predicted_fee_exact.toFixed(2);
      const conf = Math.round(prediction.confidence_score * 100);
      
      return {
        addr,
        hex: `${ensemble.replace('.', '')} ${xgb.replace('.', '')} ${lgb.replace('.', '')} ${conf.toString(16).padStart(2, '0')}00`,
        ascii: `E:${ensemble} X:${xgb} L:${lgb} C:${conf}%`,
        color: 'text-neon-green',
        isBold: true,
      };
    }
    
    // Random hex filler
    const hex = Array.from({ length: 16 }, () => 
      Math.floor(Math.random() * 256).toString(16).padStart(2, '0')
    ).join(' ');
    
    const ascii = hex.split(' ').map(h => {
      const c = parseInt(h, 16);
      return c >= 32 && c < 127 ? String.fromCharCode(c) : '.';
    }).join('');
    
    return { addr, hex, ascii, color: 'text-white/40', isBold: false };
  };

  const rows = Array.from({ length: 15 }, (_, i) => {
    const pred = predictions[i];
    return generateHexRow(i, pred);
  });

  return (
    <div className="hud-border bg-black/20 flex-1 flex flex-col relative overflow-hidden border-white/10">
      <div className="absolute top-0 left-0 w-full p-2 bg-white/5 border-b border-white/10 flex justify-between items-center text-[10px] font-bold z-10 backdrop-blur-md">
        <span>LIVE_BLOCKCHAIN_STREAM: {blockHash || 'NODE_820104'}</span>
        <span className="text-mempool-blue">
          0x{Math.random().toString(16).slice(2, 10).toUpperCase()}...
        </span>
      </div>
      
      <div 
        ref={scrollRef}
        className="scrolling-hex flex-1 overflow-auto whitespace-nowrap p-4 pt-10 text-xs leading-relaxed opacity-80 space-y-1"
      >
        {rows.map((row, i) => (
          <div key={i} className={`flex gap-4 ${row.color} ${row.isBold ? 'font-bold' : ''}`}>
            <span className="opacity-30">{row.addr}</span>
            <span className="font-mono">{row.hex}</span>
            <span>{row.ascii}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
