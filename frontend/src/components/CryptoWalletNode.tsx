import { WalletCards } from "lucide-react";

export default function CryptoWalletNode({ address, chain }: { address: string; chain?: string }) {
  return <div className="crypto-wallet-node"><WalletCards size={14} /><code>{chain || "wallet"}</code><span>{address}</span></div>;
}
