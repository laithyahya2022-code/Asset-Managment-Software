import { BadRequestException, Injectable } from '@nestjs/common';
import * as ExcelJS from 'exceljs';
import PDFDocument = require('pdfkit');

export interface TabularReport {
  title: string;
  generatedAt: Date;
  columns: Array<{ key: string; header: string; width?: number }>;
  rows: Array<Record<string, unknown>>;
}

export type ExportFormat = 'csv' | 'xlsx' | 'pdf' | 'json';

export const EXPORT_CONTENT_TYPES: Record<ExportFormat, string> = {
  csv: 'text/csv; charset=utf-8',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  pdf: 'application/pdf',
  json: 'application/json; charset=utf-8',
};

/** Renders a tabular report into CSV, XLSX, PDF or JSON. */
@Injectable()
export class ExportService {
  async render(report: TabularReport, format: ExportFormat): Promise<Buffer> {
    switch (format) {
      case 'csv':
        return this.toCsv(report);
      case 'xlsx':
        return this.toXlsx(report);
      case 'pdf':
        return this.toPdf(report);
      case 'json':
        return Buffer.from(JSON.stringify(report, null, 2), 'utf-8');
      default:
        throw new BadRequestException(`Unsupported format: ${format as string}`);
    }
  }

  private toCsv(report: TabularReport): Buffer {
    const escape = (value: unknown): string => {
      if (value === null || value === undefined) return '';
      const s = value instanceof Date ? value.toISOString() : String(value);
      return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const lines = [
      report.columns.map((c) => escape(c.header)).join(','),
      ...report.rows.map((row) => report.columns.map((c) => escape(row[c.key])).join(',')),
    ];
    // BOM so Excel opens UTF-8 CSVs correctly.
    return Buffer.from('﻿' + lines.join('\r\n'), 'utf-8');
  }

  private async toXlsx(report: TabularReport): Promise<Buffer> {
    const workbook = new ExcelJS.Workbook();
    workbook.created = report.generatedAt;
    const sheet = workbook.addWorksheet(report.title.slice(0, 31));
    sheet.columns = report.columns.map((c) => ({
      header: c.header,
      key: c.key,
      width: c.width ?? 20,
    }));
    sheet.getRow(1).font = { bold: true };
    for (const row of report.rows) sheet.addRow(row);
    return Buffer.from(await workbook.xlsx.writeBuffer());
  }

  private toPdf(report: TabularReport): Promise<Buffer> {
    return new Promise((resolve, reject) => {
      const doc = new PDFDocument({ margin: 36, size: 'A4', layout: 'landscape' });
      const chunks: Buffer[] = [];
      doc.on('data', (chunk: Buffer) => chunks.push(chunk));
      doc.on('end', () => resolve(Buffer.concat(chunks)));
      doc.on('error', reject);

      doc.fontSize(16).text(report.title, { align: 'left' });
      doc
        .fontSize(9)
        .fillColor('#666666')
        .text(`Generated ${report.generatedAt.toISOString()}`)
        .moveDown();

      const pageWidth = doc.page.width - 72;
      const colWidth = pageWidth / report.columns.length;
      const drawRow = (values: string[], bold = false) => {
        const y = doc.y;
        if (y > doc.page.height - 60) {
          doc.addPage();
        }
        doc.font(bold ? 'Helvetica-Bold' : 'Helvetica').fontSize(8).fillColor('#000000');
        values.forEach((value, i) => {
          doc.text(value, 36 + i * colWidth, doc.y, {
            width: colWidth - 6,
            lineBreak: false,
          });
          doc.moveUp();
        });
        doc.moveDown(1.2);
      };

      drawRow(report.columns.map((c) => c.header), true);
      for (const row of report.rows) {
        drawRow(
          report.columns.map((c) => {
            const value = row[c.key];
            if (value === null || value === undefined) return '';
            return value instanceof Date ? value.toISOString().slice(0, 10) : String(value);
          }),
        );
      }
      doc.end();
    });
  }
}
