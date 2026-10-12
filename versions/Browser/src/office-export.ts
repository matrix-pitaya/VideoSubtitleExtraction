import { toSimplified } from './chinese.ts';
import { safeFilename, type Segment } from './protocol.ts';

export async function officeFile(format: 'docx' | 'xlsx', title: string, segments: Segment[]): Promise<File> {
  const heading = toSimplified(title.trim() || '视频文案');
  const paragraphs = segments.map(s => toSimplified(s.text.trim())).filter(Boolean);
  const filename = safeFilename(heading) + '.' + format;
  if (format === 'docx') {
    const { Document, Packer, Paragraph, TextRun, HeadingLevel } = await import('docx');
    const document = new Document({
      creator: 'VideoSubtitleExtraction', title: heading,
      styles: { default: { document: { run: { font: '宋体', size: 24 }, paragraph: { spacing: { after: 160, line: 360 } } } } },
      sections: [{ children: [
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: '1. ' + heading, bold: true, color: '31333F', size: 30 })] }),
        ...paragraphs.flatMap(text => text.split(/\r?\n/).map(line => new Paragraph({ text: line }))),
      ] }],
    });
    return new File([await Packer.toBlob(document)], filename, { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
  }
  const { default: ExcelJS } = await import('exceljs');
  const workbook = new ExcelJS.Workbook(); workbook.creator = 'VideoSubtitleExtraction';
  const sheet = workbook.addWorksheet('视频文案', { views: [{ state: 'frozen', ySplit: 1 }] });
  sheet.columns = [{ header: '编号', key: 'number', width: 8 }, { header: '标题', key: 'title', width: 32 }, { header: '文案', key: 'text', width: 90 }];
  const body = paragraphs.join('\n');
  if (heading.length > 32767 || body.length > 32767) throw new Error('Excel 单元格最多保存 32767 个字符，请改用 Word 或 TXT 导出完整文案。');
  sheet.addRow({ number: 1, title: heading, text: body });
  sheet.autoFilter = 'A1:C2';
  sheet.eachRow(row => { row.font = { name: '宋体', size: 11 }; row.alignment = { vertical: 'top', wrapText: true }; });
  const header = sheet.getRow(1); header.height = 24;
  header.eachCell(cell => { cell.font = { name: '宋体', bold: true, color: { argb: 'FFFFFFFF' } }; cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF285C7E' } }; });
  sheet.getRow(2).height = Math.min(409, Math.max(48, (paragraphs.length + Math.ceil(body.length / 65)) * 16));
  const bytes = await workbook.xlsx.writeBuffer();
  return new File([new Uint8Array(bytes).buffer], filename, { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
}
