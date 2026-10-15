import { Document, Packer, Paragraph, TextRun } from 'docx';
import { PDFDocument, rgb, StandardFonts } from 'pdf-lib';
import { ParsedDocument } from './documentParser';
import { FoundData, anonymizeText } from './anonymizer';
import { DataCategory } from './dataCategories';

import { AnonymizationMode } from './anonymizer';

export async function exportDocument(
  document: ParsedDocument,
  foundData: FoundData[],
  categories: DataCategory[],
  mode: AnonymizationMode = 'redact'
): Promise<Blob> {
  switch (document.format) {
    case 'pdf':
      // PDF: закрашивание или удаление
      return exportPdf(document, foundData, categories, mode);
    case 'docx':
      // DOCX: всегда [censored]
      return exportDocx(document, foundData, categories, 'censored');
    case 'md':
      // MD: всегда [censored]
      return exportMarkdown(document, foundData, categories, 'censored');
    default:
      throw new Error(`Неподдерживаемый формат: ${document.format}`);
  }
}

// Поддерживаются только PDF, DOCX, MD

async function exportPdf(
  document: ParsedDocument,
  foundData: FoundData[],
  categories: DataCategory[],
  mode: AnonymizationMode = 'redact'
): Promise<Blob> {
  // Create a new PDF with anonymized text
  const pdfDoc = await PDFDocument.create();
  const font = await pdfDoc.embedFont(StandardFonts.Courier);
  
  // Build anonymized plain text based on mode
  const enabledCategories = new Set(
    categories.filter((c) => c.enabled).map((c) => c.id)
  );
  
  const dataToRedact = foundData.filter(d =>
    d.categoryId === 'custom' || enabledCategories.has(d.categoryId)
  );
  
  // Build plain text with redactions or removals
  let plainText = '';
  let lastIndex = 0;
  for (const data of dataToRedact) {
    plainText += document.text.slice(lastIndex, data.startIndex);
    
    if (mode === 'remove') {
      // Remove data completely
      plainText += '';
    } else {
      // Redact with black blocks (default for PDF)
      plainText += '█'.repeat(Math.max(data.text.length, 3));
    }
    
    lastIndex = data.endIndex;
  }
  plainText += document.text.slice(lastIndex);
  
  // Replace non-ASCII characters with █ (Courier doesn't support Cyrillic)
  const safeText = plainText.replace(/[^\x00-\x7F]/g, (char) => {
    // Keep common ASCII characters
    if (/[\x20-\x7E]/.test(char)) return char;
    return '█';
  });
  
  const page = pdfDoc.addPage([595, 842]); // A4
  const { height } = page.getSize();
  
  const lines = safeText.split('\n');
  let y = height - 50;
  const lineHeight = 14;
  const fontSize = 10;
  
  for (const line of lines) {
    if (y < 50) {
      const newPage = pdfDoc.addPage([595, 842]);
      y = newPage.getSize().height - 50;
    }
    
    const maxCharsPerLine = 80;
    const chunks = splitIntoChunks(line, maxCharsPerLine);
    
    for (const chunk of chunks) {
      page.drawText(chunk, {
        x: 50,
        y,
        size: fontSize,
        font,
        color: rgb(0, 0, 0),
      });
      y -= lineHeight;
    }
  }
  
  const pdfBytes = await pdfDoc.save();
  return new Blob([pdfBytes as unknown as BlobPart], { type: 'application/pdf' });
}

async function exportDocx(
  document: ParsedDocument,
  foundData: FoundData[],
  categories: DataCategory[],
  mode: AnonymizationMode = 'censored'
): Promise<Blob> {
  // Для DOCX всегда используем [censored]
  const lines = document.text.split('\n');
  const paragraphs: Paragraph[] = [];
  
  // For each line, create segments (normal text and [censored])
  for (const line of lines) {
    if (line.trim() === '') {
      paragraphs.push(new Paragraph({ children: [new TextRun('')] }));
      continue;
    }
    
    const runs: TextRun[] = [];
    let lastIndex = 0;
    
    // Find all found data in this line
    const lineStart = document.text.indexOf(line);
    const lineEnd = lineStart + line.length;
    
    const lineData = foundData.filter(d => {
      const isEnabled = d.categoryId === 'custom' || 
        categories.some(c => c.id === d.categoryId && c.enabled);
      return isEnabled && d.startIndex >= lineStart && d.endIndex <= lineEnd;
    });
    
    if (lineData.length === 0) {
      runs.push(new TextRun({ text: line, font: 'Courier New', size: 22 }));
    } else {
      for (const data of lineData) {
        // Add text before this data
        const beforeText = document.text.slice(lastIndex, data.startIndex);
        if (beforeText) {
          runs.push(new TextRun({ text: beforeText, font: 'Courier New', size: 22 }));
        }
        
        // Add [censored] text
        runs.push(new TextRun({
          text: '[censored]',
          font: 'Courier New',
          size: 22,
          color: 'FF0000',
          bold: true,
        }));
        
        lastIndex = data.endIndex;
      }
      
      // Add remaining text
      const remainingText = document.text.slice(lastIndex, lineEnd);
      if (remainingText) {
        runs.push(new TextRun({ text: remainingText, font: 'Courier New', size: 22 }));
      }
    }
    
    paragraphs.push(new Paragraph({ children: runs }));
  }
  
  const doc = new Document({
    sections: [{
      properties: {},
      children: paragraphs,
    }],
  });
  
  const blob = await Packer.toBlob(doc);
  return blob;
}

async function exportMarkdown(
  document: ParsedDocument,
  foundData: FoundData[],
  categories: DataCategory[],
  mode: AnonymizationMode = 'censored'
): Promise<Blob> {
  // Для MD всегда используем [censored]
  const anonymizedText = anonymizeText(document.text, foundData, categories, 'censored');
  // Remove HTML tags for markdown
  const plainText = anonymizedText.replace(/<span class="redacted"[^>]*>(.*?)<\/span>/g, '[censored]');
  const cleanText = plainText.replace(/<[^>]*>/g, '');
  
  return new Blob([cleanText], { type: 'text/markdown;charset=utf-8' });
}

function getMimeType(ext: string): string {
  const mimeTypes: Record<string, string> = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'bmp': 'image/bmp',
    'webp': 'image/webp',
    'gif': 'image/gif',
    'tiff': 'image/tiff',
    'tif': 'image/tiff',
  };
  return mimeTypes[ext] || 'image/png';
}

function splitIntoChunks(text: string, maxLen: number): string[] {
  if (text.length <= maxLen) return [text];
  const chunks: string[] = [];
  for (let i = 0; i < text.length; i += maxLen) {
    chunks.push(text.slice(i, i + maxLen));
  }
  return chunks;
}
