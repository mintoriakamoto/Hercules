/**
 * Tor proxy integration for full anonymity
 * Manages Tor circuit rotation and SOCKS5 proxy chain
 */

import { EventEmitter } from 'eventemitter3';
import { spawn, exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface TorConfig {
  socksPort: number;
  controlPort: number;
  torPath?: string;
  circuitRefreshMs?: number;
}

export interface TorEvents {
  'tor:started': void;
  'tor:stopped': void;
  'tor:circuit_rotated': { newCircuit: string };
  'tor:error': { error: Error };
}

export class TorProxy extends EventEmitter<TorEvents> {
  private config: TorConfig;
  private torProcess: any = null;
  private circuitRefreshInterval: NodeJS.Timeout | null = null;
  private isRunning = false;

  constructor(config: Partial<TorConfig> = {}) {
    super();
    this.config = {
      socksPort: config.socksPort || 9050,
      controlPort: config.controlPort || 9051,
      torPath: config.torPath || 'tor',
      circuitRefreshMs: config.circuitRefreshMs || 60000,
    };
  }

  /**
   * Start Tor daemon with SOCKS5 proxy
   */
  async start(): Promise<void> {
    if (this.isRunning) return;

    try {
      // Check if Tor is installed
      await execAsync('which tor').catch(() => {
        throw new Error('Tor not installed. Install with: apt-get install tor (Linux) or brew install tor (macOS)');
      });

      // Create torrc config
      const torrcConfig = `
SocksPort ${this.config.socksPort}
ControlPort ${this.config.controlPort}
CookieAuthentication 1
`;

      // Write temp torrc
      const fs = await import('fs/promises');
      const tmprc = '/tmp/torrc-t3mp3st';
      await fs.writeFile(tmprc, torrcConfig);

      // Start Tor process
      this.torProcess = spawn(this.config.torPath!, ['-f', tmprc], {
        detached: true,
        stdio: 'ignore',
      });

      // Wait for Tor to initialize
      await new Promise(resolve => setTimeout(resolve, 5000));

      this.isRunning = true;
      this.emit('tor:started');

      // Start circuit rotation timer
      this.startCircuitRotation();
    } catch (err) {
      this.emit('tor:error', { error: err as Error });
      throw err;
    }
  }

  /**
   * Stop Tor daemon
   */
  async stop(): Promise<void> {
    if (!this.isRunning) return;

    if (this.circuitRefreshInterval) {
      clearInterval(this.circuitRefreshInterval);
      this.circuitRefreshInterval = null;
    }

    if (this.torProcess) {
      this.torProcess.kill();
      this.torProcess = null;
    }

    this.isRunning = false;
    this.emit('tor:stopped');
  }

  /**
   * Rotate Tor circuit (get new exit IP)
   */
  async rotateCircuit(): Promise<string> {
    try {
      const { stdout } = await execAsync(
        `echo 'AUTHENTICATE ""\nSIGNAL NEWNYM\nQUIT' | nc localhost ${this.config.controlPort}`
      );
      const newIP = await this.getExitIP();
      this.emit('tor:circuit_rotated', { newCircuit: newIP });
      return newIP;
    } catch (err) {
      this.emit('tor:error', { error: err as Error });
      throw err;
    }
  }

  /**
   * Get current Tor exit IP
   */
  async getExitIP(): Promise<string> {
    try {
      const { stdout } = await execAsync(
        `curl -s --socks5 localhost:${this.config.socksPort} https://api.ipify.org`
      );
      return stdout.trim();
    } catch (err) {
      return 'unknown';
    }
  }

  /**
   * Start automatic circuit rotation
   */
  private startCircuitRotation(): void {
    if (this.circuitRefreshInterval) clearInterval(this.circuitRefreshInterval);
    this.circuitRefreshInterval = setInterval(
      () => this.rotateCircuit().catch(err => console.error('[Tor] rotation error:', err)),
      this.config.circuitRefreshMs
    );
  }

  /**
   * Get SOCKS5 proxy URL
   */
  getSocksURL(): string {
    return `socks5://localhost:${this.config.socksPort}`;
  }

  /**
   * Check if Tor is running
   */
  isActive(): boolean {
    return this.isRunning;
  }
}
