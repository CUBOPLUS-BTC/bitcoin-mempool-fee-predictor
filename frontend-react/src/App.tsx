import { useMemo } from 'react';
import { Header } from './components/Header';
import { FeeCard } from './components/FeeCard';
import { FeeChart } from './components/FeeChart';
import { HexStream } from './components/HexStream';
import { SystemLogs } from './components/SystemLogs';
import { ExecuteButton } from './components/ExecuteButton';
import { Footer } from './components/Footer';
import { CrtOverlay } from './components/CrtOverlay';
import { useApi } from './hooks/useApi';
import './App.css';

function App() {
  const {
    prediction,
    currentFees,
    health,
    logs,
    loading,
    chartData,
    fetchPrediction,
    addLog,
  } = useApi();

  const status = health?.status === 'healthy' 
    ? 'MAINNET_ONLINE' 
    : 'OFFLINE';

  const predictions = useMemo(() => {
    if (!prediction) return [];
    return [
      prediction.fee_predictions['1_block'],
      prediction.fee_predictions['3_blocks'],
      prediction.fee_predictions['6_blocks'],
    ];
  }, [prediction]);

  const handleExecute = () => {
    addLog('Manual override initiated...', 'warning');
    fetchPrediction();
  };

  // Calculate simulated metrics
  const cpuLoad = Math.floor(30 + Math.random() * 30);
  const memUsed = +(2 + Math.random()).toFixed(1);

  return (
    <div className="dark">
      <div className="relative min-h-screen lg:h-screen w-full p-2 lg:p-4 flex flex-col gap-4 overflow-x-hidden overflow-y-auto lg:overflow-hidden bg-terminal-bg text-terminal-text font-mono">
        <CrtOverlay />
        
        <Header status={status} />
        
        <div className="flex-1 flex flex-col lg:flex-row gap-4 overflow-visible lg:overflow-hidden z-40">
          {/* Left Sidebar - Fee Cards */}
          <aside className="w-full lg:w-64 flex flex-col sm:flex-row lg:flex-col gap-4 shrink-0">
            <FeeCard
              title="Priority_Low"
              prediction={prediction?.fee_predictions['6_blocks']}
              networkFee={currentFees?.fees.hour}
              priority="low"
            />
            <FeeCard
              title="Priority_Med"
              prediction={prediction?.fee_predictions['3_blocks']}
              networkFee={currentFees?.fees.half_hour}
              priority="medium"
            />
            <FeeCard
              title="Priority_High"
              prediction={prediction?.fee_predictions['1_block']}
              networkFee={currentFees?.fees.fastest}
              priority="high"
            />
          </aside>

          {/* Main Content */}
          <main className="flex-1 flex flex-col gap-4 min-h-[500px] lg:min-h-0 lg:overflow-hidden">
            <HexStream 
              predictions={predictions}
              blockHash={prediction?.mempool_snapshot ? 
                `0x${prediction.mempool_snapshot.tx_count.toString(16).toUpperCase().slice(0, 8)}` : 
                undefined
              }
            />
            
            {/* Shadow Deployment Chart */}
            <div className="flex-1 min-h-[250px] lg:min-h-0 border border-terminal-border bg-terminal-bg/50 rounded p-3">
              <FeeChart data={chartData} />
            </div>
            
            <ExecuteButton onClick={handleExecute} loading={loading} />
          </main>

          {/* Right Sidebar - Logs */}
          <aside className="w-full lg:w-72 flex flex-col min-h-[300px] lg:min-h-0 z-40 shrink-0 mb-4 lg:mb-0">
            <SystemLogs 
              logs={logs} 
              cpuLoad={cpuLoad}
              memUsed={memUsed}
            />
          </aside>
        </div>

        <Footer latestBlock={prediction?.mempool_snapshot?.blocks_last_hour} />
      </div>
    </div>
  );
}

export default App;
