import { useMemo } from 'react';
import { Header } from './components/Header';
import { FeeCard } from './components/FeeCard';
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
      <div className="relative h-screen w-screen p-4 flex flex-col gap-4 overflow-hidden bg-terminal-bg text-terminal-text font-mono">
        <CrtOverlay />
        
        <Header status={status} />
        
        <div className="flex-1 flex gap-4 overflow-hidden z-40">
          {/* Left Sidebar - Fee Cards */}
          <aside className="w-64 flex flex-col gap-4">
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
          <main className="flex-1 flex flex-col gap-4 overflow-hidden">
            <HexStream 
              predictions={predictions}
              blockHash={prediction?.mempool_snapshot ? 
                `0x${prediction.mempool_snapshot.tx_count.toString(16).toUpperCase().slice(0, 8)}` : 
                undefined
              }
            />
            <ExecuteButton onClick={handleExecute} loading={loading} />
          </main>

          {/* Right Sidebar - Logs */}
          <aside className="w-72 flex flex-col z-40">
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
