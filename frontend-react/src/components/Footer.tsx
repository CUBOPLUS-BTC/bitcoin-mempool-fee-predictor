interface FooterProps {
  latestBlock?: number;
}

export function Footer({ latestBlock }: FooterProps) {
  return (
    <footer className="hud-border bg-black/40 backdrop-blur-sm p-3 lg:px-6 lg:py-2 flex flex-col sm:flex-row justify-between items-center text-[10px] z-40 border-white/10 gap-2 sm:gap-0">
      <div className="flex gap-8">
        <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer" className="hover:text-mempool-blue hover:underline">
          &gt; SWAGGER_UI
        </a>
        <a href="http://localhost:8000/redoc" target="_blank" rel="noopener noreferrer" className="hover:text-mempool-yellow hover:underline">
          &gt; API_ENDPOINT
        </a>
        <a href="#" className="hover:text-mempool-orange hover:underline">
          &gt; SYSTEM_MAP
        </a>
      </div>
      
      <div className="flex items-center gap-4">
        <span className="opacity-50 uppercase">Blockchain Data Protocol</span>
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 bg-mempool-orange animate-blink" />
          <span className="text-mempool-orange">
            LATEST_BLOCK: {latestBlock || '820104'}
          </span>
        </div>
      </div>
    </footer>
  );
}
