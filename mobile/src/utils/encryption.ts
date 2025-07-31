import CryptoJS from 'crypto-js';
import DeviceInfo from 'react-native-device-info';

class EncryptionService {
  private secretKey: string;

  constructor() {
    // Generate a device-specific key
    this.secretKey = this.generateDeviceKey();
  }

  private generateDeviceKey(): string {
    const deviceId = DeviceInfo.getUniqueId();
    const bundleId = DeviceInfo.getBundleId();
    return CryptoJS.SHA256(`${deviceId}-${bundleId}-auraconnect`).toString();
  }

  encrypt(data: any): string {
    try {
      const jsonString = JSON.stringify(data);
      return CryptoJS.AES.encrypt(jsonString, this.secretKey).toString();
    } catch (error) {
      console.error('Encryption failed:', error);
      throw new Error('Failed to encrypt data');
    }
  }

  decrypt(encryptedData: string): any {
    try {
      const decrypted = CryptoJS.AES.decrypt(encryptedData, this.secretKey);
      const jsonString = decrypted.toString(CryptoJS.enc.Utf8);
      return JSON.parse(jsonString);
    } catch (error) {
      console.error('Decryption failed:', error);
      throw new Error('Failed to decrypt data');
    }
  }

  encryptSensitiveFields(data: any, fields: string[]): any {
    const clonedData = { ...data };
    
    fields.forEach(field => {
      if (clonedData[field] !== undefined) {
        clonedData[field] = this.encrypt(clonedData[field]);
      }
    });

    return clonedData;
  }

  decryptSensitiveFields(data: any, fields: string[]): any {
    const clonedData = { ...data };
    
    fields.forEach(field => {
      if (clonedData[field] !== undefined) {
        try {
          clonedData[field] = this.decrypt(clonedData[field]);
        } catch {
          // If decryption fails, leave the field as is
        }
      }
    });

    return clonedData;
  }
}

export const encryptionService = new EncryptionService();