import * as OpenCC from 'opencc-js/t2cn';

// Bundle the dictionary locally; conversion never sends text to a service.
const convert = OpenCC.Converter({ from: 'tw', to: 'cn' });
export const toSimplified = (text: string): string => convert(text);
