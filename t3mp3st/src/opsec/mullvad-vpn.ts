/**
 * Mullvad VPN integration for always-on anonymity
 * Ensures all traffic is routed through Mullvad before any tool execution
 */

import { EventEmitter } from 'eventemitter3';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface MullvadConfig {
  autoConnect?: boolean;
  exitCountry?: string;
  wireguardKey?: string;
  checkIntervalMs?: number;
}

export interface MullvadEvents {
  'vpn:connected': { server: string; ip: string };
  'vpn:disconnected': void;
  'vpn:status': { connected: boolean; ip: string; server: string };
  'vpn:error': { error: Error };
}

export class MullvadVPN extends EventEmitter<MullvadEvents> {
  private config: MullvadConfig;
  private statusCheckInterval: NodeJS.Timeout | null = null;
  private isConnected = false;

  constructor(config: Partial<MullvadConfig> = {}) {
    super();
    this.config = {
      autoConnect: config.autoConnect ?? true,
      exitCountry: config.exitCountry || 'SE', // Sweden by default (privacy-friendly)
      checkIntervalMs: config.checkIntervalMs || 30000,
    };
  }

  /**
   * Check if Mullvad is installed and available
   */
  async checkInstalled(): Promise<boolean> {
    try {
      await execAsync('which mullvad');
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Connect to Mullvad VPN
   */
  async connect(): Promise<{ server: string; ip: string }> {
    try {
      if (this.config.autoConnect) {
        await execAsync('mullvad connect');
      }

      const status = await this.getStatus();
      this.isConnected = status.connected;

      if (this.isConnected) {
        this.emit('vpn:connected', { server: status.server, ip: status.ip });
      }

      return { server: status.server, ip: status.ip };
    } catch (err) {
      this.emit('vpn:error', { error: err as Error });
      throw err;
    }
  }

  /**
   * Disconnect from Mullvad VPN
   */
  async disconnect(): Promise<void> {
    try {
      await execAsync('mullvad disconnect');
      this.isConnected = false;
      this.emit('vpn:disconnected');
    } catch (err) {
      this.emit('vpn:error', { error: err as Error });
      throw err;
    }
  }

  /**
   * Get VPN connection status
   */
  async getStatus(): Promise<{ connected: boolean; ip: string; server: string }> {
    try {
      const { stdout } = await execAsync('mullvad status');
      const connected = stdout.includes('Connected');
      const ipMatch = stdout.match(/\d+\.\d+\.\d+\.\d+/);
      const serverMatch = stdout.match(/Server: ([^\n]+)/);

      return {
        connected,
        ip: ipMatch ? ipMatch[0] : 'unknown',
        server: serverMatch ? serverMatch[1].trim() : 'unknown',
      };
    } catch {
      return { connected: false, ip: 'unknown', server: 'unknown' };
    }
  }

  /**
   * Set exit country for VPN
   */
  async setExitCountry(country: string): Promise<void> {
    try {
      await execAsync(`mullvad relay set location ${country}`);
      this.config.exitCountry = country;
    } catch (err) {
      this.emit('vpn:error', { error: err as Error });
      throw err;
    }
  }

  /**
   * Rotate to random exit location
   */
  async rotateLocation(): Promise<string> {
    try {
      const { stdout } = await execAsync('mullvad relay set location random');
      const match = stdout.match(/Country: (\w+)/);
      return match ? match[1] : 'random';
    } catch (err) {
      this.emit('vpn:error', { error: err as Error });
      throw err;
    }
  }

  /**
   * Start periodic status checks
   */
  startStatusChecks(): void {
    if (this.statusCheckInterval) clearInterval(this.statusCheckInterval);
    this.statusCheckInterval = setInterval(async () => {
      const status = await this.getStatus();
      this.isConnected = status.connected;
      this.emit('vpn:status', status);

      // Auto-reconnect if disconnected
      if (!this.isConnected && this.config.autoConnect) {
        try {
          await this.connect();
        } catch (err) {
          console.error('[Mullvad] auto-reconnect failed:', err);
        }
      }
    }, this.config.checkIntervalMs);
  }

  /**
   * Stop status checks
   */
  stopStatusChecks(): void {
    if (this.statusCheckInterval) {
      clearInterval(this.statusCheckInterval);
      this.statusCheckInterval = null;
    }
  }

  /**
   * Get current connection status
   */
  isActive(): boolean {
    return this.isConnected;
  }
}
