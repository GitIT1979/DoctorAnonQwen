import { Document, Packer, Paragraph, TextRun } from 'docx';
import { PDFDocument, rgb, StandardFonts } from 'pdf-lib';
import { ParsedDocument, OcrWord } from './documentParser';
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
    case 'image':
      return exportImage(document, foundData, categories, mode);
    case 'pdf':
      return exportPdf(document, foundData, categories, mode);
    case 'docx':
      return exportDocx(document, foundData, categories, mode);
    case 'md':
      return exportMarkdown(document, foundData, categories, mode);
    default:
      throw new Error(`Неподдерживаемый формат: ${document.format}`);
  }
}

async function exportImage(
  document: ParsedDocument,
  foundData: FoundData[],
  categories: DataCategory[],
  mode: AnonymizationMode = 'redact'
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = window.document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('Не удалось создать canvas'));
        return;
      }
      
      // Draw original image
      ctx.drawImage(img, 0, 0);
      
      // Get enabled categories
      const enabledCategories = new Set(
        categories.filter((c) => c.enabled).map((c) => c.id)
      );
      
      // Find which OCR words to redact
      const wordsToRedact = findWordsToRedact(document, foundData, enabledCategories);
      
      // Draw black rectangles over found words
      ctx.fillStyle = '#000000';
      for (const word of wordsToRedact) {
        ctx.fillRect(
          word.bbox.x0,
          word.bbox.y0,
          word.bbox.x1 - word.bbox.x0,
          word.bbox.y1 - word.bbox.y0
        );
      }
      
      // Export based on original format
      const ext = document.filename.split('.').pop()?.toLowerCase() || 'png';
      const mimeType = getMimeType(ext);
      
      canvas.toBlob((blob) => {
        if (blob) resolve(blob);
        else reject(new Error('Не удалось экспортировать изображение'));
      }, mimeType, 0.95);
    };
    img.onerror = reject;
    img.src = document.imageData || '';
  });
}

function findWordsToRedact(
  document: ParsedDocument,
  foundData: FoundData[],
  enabledCategories: Set<string>
): OcrWord[] {
  if (!document.ocrWords || document.ocrWords.length === 0) return [];
  
  const wordsToRedact: OcrWord[] = [];
  const text = document.text;
  
  // For each found data, find corresponding OCR words
  const dataToRedact = foundData.filter(d => 
    d.categoryId === 'custom' || enabledCategories.has(d.categoryId)
  );
  
  for (const data of dataToRedact) {
    const dataText = data.text.toLowerCase().trim();
    
    // Find OCR words that overlap with this data
    for (const word of document.ocrWords) {
      const wordText = word.text.toLowerCase().trim();
      if (wordText.length < 2) continue;
      
      // Check if word is part of the found data
      if (dataText.includes(wordText) || wordText.includes(dataText.split(' ')[0])) {
        // Check if this word's text appears in the found data range
        const wordPosInText = text.toLowerCase().indexOf(wordText);
        if (wordPosInText >= data.startIndex && wordPosInText < data.endIndex) {
          wordsToRedact.push(word);
        }
      }
    }
  }
  
  return wordsToRedact;
}

async function exportPdf(
  document: ParsedDocument,
  foundData: FoundData[],
  categories: DataCategory[],
  mode: AnonymizationMode = 'redact'
): Promise<Blob> {
  // Create a new PDF with anonymized text
  const pdfDoc = await PDFDocument.create();
  const font = await pdfDoc.embedFont(StandardFonts.Courier);
  
  // Build anonymized plain text with █ for redacted parts
  const enabledCategories = new Set(
    categories.filter((c) => c.enabled).map((c) => c.id)
  );
  
  const dataToRedact = foundData.filter(d =>
    d.categoryId === 'custom' || enabledCategories.has(d.categoryId)
  );
  
  // Build plain text with redactions
  let plainText = '';
  let lastIndex = 0;
  for (const data of dataToRedact) {
    plainText += document.text.slice(lastIndex, data.startIndex);
    plainText += '█'.repeat(Math.max(data.text.length, 3));
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
  mode: AnonymizationMode = 'redact'
): Promise<Blob> {
  const anonymizedText = anonymizeText(document.text, foundData, categories);
  
  // Parse the anonymized HTML to create docx paragraphs
  const lines = document.text.split('\n');
  const paragraphs: Paragraph[] = [];
  
  // For each line, create segments (normal text and redacted text)
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
        
        // Add redacted text (black block)
        const redactedText = '█'.repeat(Math.max(data.text.length, 3));
        runs.push(new TextRun({
          text: redactedText,
          font: 'Courier New',
          size: 22,
          color: '000000',
          shading: { type: 'clear', fill: '000000', color: '000000' },
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
  mode: AnonymizationMode = 'redact'
): Promise<Blob> {
  const anonymizedText = anonymizeText(document.text, foundData, categories);
  // Remove HTML tags for markdown
  const plainText = anonymizedText.replace(/<span class="redacted"[^>]*>(.*?)<\/span>/g, '███');
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
