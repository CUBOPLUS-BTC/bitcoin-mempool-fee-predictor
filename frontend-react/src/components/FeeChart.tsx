import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import type { ChartDataPoint } from '../hooks/useApi';

interface FeeChartProps {
  data: ChartDataPoint[];
}

export function FeeChart({ data }: FeeChartProps) {
  const chartData = useMemo(() => {
    return data.map((point, index) => ({
      ...point,
      index,
      // Format timestamp for display
      time: new Date(point.timestamp).toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
      }),
    }));
  }, [data]);

  // Calculate statistics
  const stats = useMemo(() => {
    if (data.length < 2) return null;
    
    const diffs = data.map(d => d.predicted_1block - d.mempool_fastest);
    const avgDiff = diffs.reduce((a, b) => a + b, 0) / diffs.length;
    const maxDiff = Math.max(...diffs.map(Math.abs));
    
    return {
      avgDiff: avgDiff.toFixed(2),
      maxDiff: maxDiff.toFixed(2),
      bias: avgDiff > 0 ? 'overestimates' : 'underestimates',
    };
  }, [data]);

  if (data.length < 2) {
    return (
      <div className="h-full flex items-center justify-center text-terminal-dim text-sm">
        <div className="text-center">
          <div className="mb-2 text-terminal-accent">⏳ COLLECTING DATA</div>
          <div className="text-xs">Waiting for shadow deployment samples...</div>
          <div className="text-xs mt-1">({data.length}/2 samples)</div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header with stats */}
      <div className="flex justify-between items-center mb-2 px-1">
        <div className="text-xs text-terminal-dim">
          <span className="text-terminal-accent">SHADOW DEPLOYMENT</span>
          <span className="mx-2">|</span>
          <span>Last {data.length} samples</span>
        </div>
        {stats && (
          <div className="text-xs text-terminal-dim">
            <span>ML {stats.bias} by avg </span>
            <span className={parseFloat(stats.avgDiff) > 0 ? 'text-red-400' : 'text-green-400'}>
              {parseFloat(stats.avgDiff) > 0 ? '+' : ''}{stats.avgDiff} sat/vB
            </span>
            <span className="mx-1">|</span>
            <span>Max Δ: {stats.maxDiff}</span>
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid 
              strokeDasharray="3 3" 
              stroke="rgba(0, 255, 65, 0.1)"
            />
            <XAxis 
              dataKey="time" 
              stroke="rgba(0, 255, 65, 0.5)"
              tick={{ fill: 'rgba(0, 255, 65, 0.6)', fontSize: 10, fontFamily: 'monospace' }}
              tickLine={{ stroke: 'rgba(0, 255, 65, 0.3)' }}
            />
            <YAxis 
              stroke="rgba(0, 255, 65, 0.5)"
              tick={{ fill: 'rgba(0, 255, 65, 0.6)', fontSize: 10, fontFamily: 'monospace' }}
              tickLine={{ stroke: 'rgba(0, 255, 65, 0.3)' }}
              label={{ 
                value: 'sat/vB', 
                angle: -90, 
                position: 'insideLeft',
                fill: 'rgba(0, 255, 65, 0.5)',
                fontSize: 10,
              }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(0, 20, 0, 0.95)',
                border: '1px solid rgba(0, 255, 65, 0.5)',
                borderRadius: '4px',
                fontFamily: 'monospace',
                fontSize: '11px',
              }}
              labelStyle={{ color: 'rgba(0, 255, 65, 0.8)' }}
              itemStyle={{ fontSize: '11px' }}
            />
            <Legend 
              wrapperStyle={{ 
                fontSize: '10px', 
                fontFamily: 'monospace',
                paddingTop: '10px',
              }}
            />
            
            {/* ML Predictions */}
            <Line
              type="monotone"
              dataKey="predicted_1block"
              name="ML (1-block)"
              stroke="#00ff41"
              strokeWidth={2}
              dot={{ fill: '#00ff41', strokeWidth: 0, r: 2 }}
              activeDot={{ r: 4, stroke: '#00ff41', strokeWidth: 2, fill: '#000' }}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="predicted_3blocks"
              name="ML (3-blocks)"
              stroke="#00aa41"
              strokeWidth={1.5}
              dot={{ fill: '#00aa41', strokeWidth: 0, r: 2 }}
              isAnimationActive={false}
              strokeDasharray="4 4"
            />
            
            {/* Mempool.space (Reality) */}
            <Line
              type="monotone"
              dataKey="mempool_fastest"
              name="Mempool.space (Actual)"
              stroke="#ff6b6b"
              strokeWidth={2}
              dot={{ fill: '#ff6b6b', strokeWidth: 0, r: 2 }}
              activeDot={{ r: 4, stroke: '#ff6b6b', strokeWidth: 2, fill: '#000' }}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="mempool_halfhour"
              name="Mempool.space (30min)"
              stroke="#ffaa6b"
              strokeWidth={1.5}
              dot={{ fill: '#ffaa6b', strokeWidth: 0, r: 2 }}
              isAnimationActive={false}
              strokeDasharray="4 4"
            />
            
            {/* Zero line reference */}
            <ReferenceLine 
              y={0} 
              stroke="rgba(0, 255, 65, 0.2)" 
              strokeDasharray="2 2" 
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Legend explanation */}
      <div className="mt-2 px-1 text-xs text-terminal-dim flex gap-4">
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-[#00ff41]"></div>
          <span>ML Predictions</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-[#ff6b6b]"></div>
          <span>Actual (mempool.space)</span>
        </div>
      </div>
    </div>
  );
}
