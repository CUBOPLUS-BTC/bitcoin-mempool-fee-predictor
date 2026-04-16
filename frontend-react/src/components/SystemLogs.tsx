import type { LogEntry, LogType } from '../types/api';

interface SystemLogsProps {
  logs: LogEntry[];
  cpuLoad: number;
  memUsed: number;
}

const logColors: Record<LogType, string> = {
  info: 'text-white/40',
  warning: 'text-mempool-orange',
  error: 'text-red-500',
  success: 'text-neon-green',
};

export function SystemLogs({ logs, cpuLoad, memUsed }: SystemLogsProps) {
  return (
    <div className="hud-border bg-black/60 p-4 flex-1 overflow-hidden flex flex-col border-white/10">
      <div className="text-[10px] font-bold border-b border-white/20 pb-1 mb-2">
        SYSTEM_LOGS
      </div>
      
      <div className="text-[9px] font-mono space-y-2 opacity-80 overflow-y-auto flex-1">
        {logs.map((log, i) => (
          <p key={i} className={logColors[log.type]}>
            [{log.time}] {log.msg}
          </p>
        ))}
      </div>
      
      <div className="mt-auto pt-4 flex flex-col gap-2">
        <div className="flex justify-between text-[10px]">
          <span>CPU_LOAD</span>
          <span>{cpuLoad}%</span>
        </div>
        <div className="w-full bg-white/10 h-1">
          <div 
            className="bg-white h-full shadow-[0_0_8px_white] transition-all duration-500"
            style={{ width: `${cpuLoad}%` }}
          />
        </div>
        
        <div className="flex justify-between text-[10px] mt-1">
          <span>MEM_USED</span>
          <span>{memUsed}GB</span>
        </div>
        <div className="w-full bg-white/10 h-1">
          <div 
            className="bg-white h-full shadow-[0_0_8px_white] transition-all duration-500"
            style={{ width: `${(memUsed / 4) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}
