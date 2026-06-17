# Basic Flow Example

This example demonstrates the simplest possible Workbench flow: transforming text input to uppercase output.

## Flow Structure

```
input-data → string-case → output-data
```

- **input-data**: Receives text input via the "text" key
- **string-case**: Transforms the text to uppercase
- **output-data**: Returns the result via the "result" key

## How to Run

```bash
cd sdks/nodejs/examples/01-basic-flow
node run.js
```

## Expected Output

```
🚀 Running Basic Flow Example
================================
📥 Input: { text: "hello world" }
📤 Output: { result: "HELLO WORLD" }
⏱️  Execution time: 5 ms
✅ Status: Completed.
```

## What This Demonstrates

- Basic flow execution with `Workbench.create()` and `engine.run()`
- Simple input/output handling
- Text transformation using built-in nodes
- Execution timeline and performance metrics