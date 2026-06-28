"use client";
import "@rainbow-me/rainbowkit/styles.css";
import { getDefaultConfig, RainbowKitProvider, darkTheme } from "@rainbow-me/rainbowkit";
import { WagmiProvider } from "wagmi";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";

const queryClient = new QueryClient();

function wagmiConfig() {
  const chainId = parseInt(process.env.NEXT_PUBLIC_CHAIN_ID || "11155111", 10);
  const chains: any[] = [];
  if (chainId === 1) {
    const { mainnet } = require("wagmi/chains");
    chains.push(mainnet);
  } else if (chainId === 137) {
    const { polygon } = require("wagmi/chains");
    chains.push(polygon);
  } else if (chainId === 42161) {
    const { arbitrum } = require("wagmi/chains");
    chains.push(arbitrum);
  } else {
    const { sepolia } = require("wagmi/chains");
    chains.push(sepolia);
  }
  return getDefaultConfig({
    appName: "TradingGame",
    projectId: process.env.NEXT_PUBLIC_WC_PROJECT_ID || "c5f12576ebf4055a9edf822b451794a5",
    chains,
    ssr: true,
  });
}

export function Providers({ children }: { children: ReactNode }) {
  return (
    <WagmiProvider config={wagmiConfig()}>
      <QueryClientProvider client={queryClient}>
        <RainbowKitProvider theme={darkTheme({ accentColor: "#16c784" })}>
          {children}
        </RainbowKitProvider>
      </QueryClientProvider>
    </WagmiProvider>
  );
}
