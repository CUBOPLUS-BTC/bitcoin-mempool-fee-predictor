import { Cpu } from 'lucide-react';

interface ExecuteButtonProps {
  onClick: () => void;
  loading: boolean;
}

export function ExecuteButton({ onClick, loading }: ExecuteButtonProps) {
  return (
    <div className="p-6 bg-black/80 border-t border-white/20 flex flex-col items-center justify-center gap-4">
      <div className="text-[10px] tracking-[0.3em] opacity-80 uppercase mb-2">
        Manual Override Required
      </div>
      
      <button
        onClick={onClick}
        disabled={loading}
        className="hud-border bg-black border-mempool-orange px-12 py-4 text-lg font-bold text-mempool-orange 
                   hover:bg-mempool-orange hover:text-black transition-all group flex items-center gap-4
                   disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <Cpu className={`w-6 h-6 group-hover:scale-110 transition-transform ${loading ? 'animate-spin' : ''}`} />
        {loading ? 'EXECUTING...' : 'EXECUTE: ML_PREDICTION_MODEL'}
      </button>
      
      <div className="text-[10px] font-mono mt-2 flex gap-4">
        <span className="opacity-50">CURS_POS: 42.122</span>
        <span className="opacity-50">EXEC_PATH: /usr/bin/kv_predict</span>
        <span className="animate-blink text-mempool-orange">_</span>
      </div>
    </div>
  );
}
