export function CrtOverlay() {
  return (
    <>
      {/* CRT Scanline Effect */}
      <div 
        className="fixed inset-0 pointer-events-none z-50"
        style={{
          background: `
            linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%),
            linear-gradient(90deg, rgba(255, 0, 0, 0.03), rgba(0, 255, 0, 0.01), rgba(0, 0, 255, 0.03))
          `,
          backgroundSize: '100% 2px, 3px 100%',
        }}
      />
      
      {/* Background Binary Pattern */}
      <div className="fixed inset-0 pointer-events-none opacity-[0.02] text-[8px] font-mono overflow-hidden leading-none z-0">
        {Array.from({ length: 20 }, (_, i) => (
          <div key={i}>
            {i % 4 === 0 
              ? '01011010101011110101010101011110101010101011110101010101011110101010101011110101010101011110101'
              : i % 4 === 1
              ? '10101011010101011010111101010101010111101010101010111101010101010111101010101010111101010101'
              : i % 4 === 2
              ? '[BLOCK_CHAIN_RAW_DATA_HEX_VAL_0x44_0x55_0x66_0x77_0x88_0x99_0xAA_0xBB_0xCC_0xDD_0xEE_0xFF]'
              : 'KINETIC_VOID_KINETIC_VOID_KINETIC_VOID_KINETIC_VOID_KINETIC_VOID_KINETIC_VOID'
            }
          </div>
        ))}
      </div>
    </>
  );
}
