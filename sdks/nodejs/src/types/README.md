# Custom Type Conversions

This directory contains type definitions (`.json` files) and optional type converters (`.converters.js` files) for custom types in the zv1 SDK.

## Type Definitions

Each type is defined by a JSON schema file (e.g., `message.json`, `conversation.json`). These schemas are used to validate values at runtime.

## Type Converters

Type converters allow you to define conversion operations for custom types, such as converting a `message` object to a string.

### Default Converters

The SDK includes default converter files for common types in this directory:

- **`message.converters.js`**: Converts to string by extracting all text from `message.content` array
- **`conversation.converters.js`**: Converts array of messages to string, joining with separator
- **`content.converters.js`**: Extracts text from content objects/arrays
- **`tool.converters.js`**: Converts tool objects to string representation
- **`plugin.converters.js`**: Converts plugin objects to string representation

You can override any of these by modifying the corresponding `.converters.js` file.

### Using Converters

You can use type converters in your code:

```javascript
import zv1 from 'zv1';

const engine = await zv1.create('./myflow.zv1', config);

// Convert a message to string
const message = {
  role: 'user',
  content: [
    { type: 'text', text: 'Hello' },
    { type: 'text', text: ' World' }
  ]
};

const text = engine.convertType(message, 'message');
// Result: "Hello World"
```

### Creating Custom Converters

To define converters for a type, create a `<typeName>.converters.js` file in this directory. Each type should have its own converter file.

**Example: `message.converters.js`**

```javascript
/**
 * Type converters for the 'message' type
 * Converts message objects to strings by extracting all text content
 */

/**
 * Extract text content from a message's content field
 */
function extractTextFromContent(content) {
  if (typeof content === 'string') {
    return content;
  }
  
  if (content === null || content === undefined) {
    return '';
  }
  
  if (Array.isArray(content)) {
    let text = '';
    for (const item of content) {
      if (item && typeof item === 'object' && item.type === 'text' && item.text) {
        text += item.text;
      }
    }
    return text;
  }
  
  return String(content || '');
}

/**
 * Convert a message object to a string
 */
export function toString(message, separator) {
  if (!message || typeof message !== 'object') {
    return String(message || '');
  }
  
  return extractTextFromContent(message.content);
}

export default {
  toString
};
```

### Converter Functions

Each converter file should export an object with conversion functions. Common conversions:

- **`toString(value, options)`**: Converts the value to a string
  - `value`: The value to convert
  - `options`: Optional object with conversion options (e.g., `{ separator: '\n' }`)


- **`toBoolean(value)`**: (Message only) Converts message to boolean
  - `value`: The message to convert
  - Returns true if message has content

### How It Works

1. When you call `engine.convertType(value, 'message')`, the engine:
   - Checks if a custom converter file exists (`message.converters.js`)
   - Falls back to built-in converters if available
   - Falls back to default `String()` conversion

2. The converter system is extensible - you can override built-in converters or add converters for new types.

### Examples

**Converting a message:**
```javascript
const message = {
  role: 'assistant',
  content: [
    { type: 'text', text: 'Hello, ' },
    { type: 'text', text: 'how can I help?' }
  ]
};

const text = engine.convertType(message, 'message');
// Returns: "Hello, how can I help?"
```

**Converting a conversation to string (YAML-like chat log format):**
```javascript
const conversation = [
  { 
    role: 'user', 
    content: [
      { type: 'text', text: 'Hello' },
      { type: 'image_url', image_url: { url: 'https://example.com/image.png' } }
    ]
  },
  { 
    role: 'assistant', 
    content: 'Hi there! Here is the image you requested.' 
  },
  {
    role: 'tool',
    tool_call_id: 'call_123',
    content: [{ type: 'tool_result', result: 'Success' }]
  }
];

const chatLog = engine.convertType(conversation, 'conversation');
// Returns:
// user:
//   Hello [image_url: https://example.com/image.png]
//
// assistant:
//   Hi there! Here is the image you requested.
//
// tool:
//   [tool_result: Success] [tool_call_id: call_123]
```

**Converting content:**
```javascript
const content = [
  { type: 'text', text: 'First paragraph' },
  { type: 'text', text: 'Second paragraph' }
];

const text = engine.convertType(content, 'content');
// Returns: "First paragraphSecond paragraph"
```

