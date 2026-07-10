import { Injectable } from '@nestjs/common';
import * as bwipjs from 'bwip-js';
import * as QRCode from 'qrcode';

/**
 * Label generation: QR codes and Code-128 barcodes as PNG buffers,
 * ready for label printers or on-screen scanning. The payload is the
 * asset tag — scanning resolves it via GET /assets/scan/{code}.
 */
@Injectable()
export class LabelsService {
  qrCodePng(payload: string, size = 300): Promise<Buffer> {
    return QRCode.toBuffer(payload, {
      type: 'png',
      width: size,
      errorCorrectionLevel: 'M',
      margin: 2,
    });
  }

  qrCodeDataUrl(payload: string): Promise<string> {
    return QRCode.toDataURL(payload, { errorCorrectionLevel: 'M', margin: 2 });
  }

  barcodePng(payload: string): Promise<Buffer> {
    return bwipjs.toBuffer({
      bcid: 'code128',
      text: payload,
      scale: 3,
      height: 12,
      includetext: true,
      textxalign: 'center',
    });
  }
}
