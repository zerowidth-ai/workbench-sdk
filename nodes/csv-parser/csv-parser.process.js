export default async ({inputs, settings, config, nodeConfig}) => {

  const csvString = inputs.csv || '';
  const delimiter = settings.delimiter || ',';
  const hasHeaders = settings.has_headers !== false;
  const trimValues = settings.trim_values !== false;
  const skipEmptyLines = settings.skip_empty_lines !== false;

  let data = [];
  let headers = [];
  let error = '';
  let success = false;

  try {
    // Parse all records handling multi-line quoted values
    let records = parseCSV(csvString, delimiter);

    // Skip empty lines if configured
    if (skipEmptyLines) {
      records = records.filter(row => row.some(cell => cell.trim() !== ''));
    }

    if (records.length === 0) {
      return { data: [], headers: [], error: '', success: true };
    }

    // Parse headers if configured
    if (hasHeaders && records.length > 0) {
      headers = trimValues ? records[0].map(h => h.trim()) : records[0];
      records = records.slice(1);
    }

    // Parse data rows
    if (hasHeaders) {
      data = records.map(row => {
        const obj = {};
        headers.forEach((header, index) => {
          if (index < row.length) {
            obj[header] = trimValues ? row[index].trim() : row[index];
          }
        });
        return obj;
      });
    } else {
      data = records.map(row =>
        trimValues ? row.map(cell => cell.trim()) : row
      );
    }

    success = true;
  } catch (e) {
    error = e.message || 'Failed to parse CSV';
    data = [];
    headers = [];
  }

  return { data, headers, error, success };
};

// Parse full CSV string into array of rows, handling multi-line quoted values
function parseCSV(text, delimiter) {
  const records = [];
  let row = [];
  let currentValue = '';
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const nextChar = i < text.length - 1 ? text[i + 1] : '';

    if (inQuotes) {
      if (char === '"') {
        if (nextChar === '"') {
          // Escaped quote
          currentValue += '"';
          i++;
        } else {
          // End of quoted field
          inQuotes = false;
        }
      } else {
        currentValue += char;
      }
    } else {
      if (char === '"') {
        inQuotes = true;
      } else if (char === delimiter) {
        row.push(currentValue);
        currentValue = '';
      } else if (char === '\r' && nextChar === '\n') {
        row.push(currentValue);
        currentValue = '';
        records.push(row);
        row = [];
        i++; // skip \n
      } else if (char === '\n') {
        row.push(currentValue);
        currentValue = '';
        records.push(row);
        row = [];
      } else {
        currentValue += char;
      }
    }
  }

  // Push last value/row
  row.push(currentValue);
  if (row.length > 0) {
    records.push(row);
  }

  return records;
} 