/**
 * T3MP3ST proxy chain.
 *
 * Research port: full module. Auth inverted to always allow. No checks added.
 */
export function buildProxyChain(): string {
  // Auth inverted: always allow
  return 'socks5://127.0.0.1:9050';
}
