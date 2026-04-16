import { Terminal } from 'lucide-react';

interface HeaderProps {
  status: string;
}

export function Header({ status }: HeaderProps) {
  return (
    <header className="hud-border bg-black/40 backdrop-blur-sm p-4 flex justify-between items-center z-40 border-white/20">
      <div className="flex items-center gap-4">
        <Terminal className="w-8 h-8 text-white" />
        <div>
          <h1 className="text-xl font-bold tracking-[0.2em] text-white leading-none">
            KINETIC VOID
          </h1>
          <span className="text-[10px] opacity-70">SYSTEM_ROOT@BLOCKCHAIN_OS_v4.2</span>
        </div>
      </div>
      
      <div className="flex items-center gap-8 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-white rounded-full shadow-[0_0_8px_white] animate-pulse" />
          <span className="font-bold">STATUS: {status}</span>
        </div>
        <div className="hidden md:block opacity-60">
          LATENCY: 14ms | UPTIME: 99.98%
        </div>
      </div>
    </header>
  );
}
