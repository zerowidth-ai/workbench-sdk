import fs from "fs";
import path from "path";
import assert from "assert";
import Ajv from "ajv";
import dotenv from "dotenv";
dotenv.config();

// utils/paths.js
import { fileURLToPath } from 'url';
import { dirname } from 'path';

export function getFilename(metaUrl) {
  return fileURLToPath(metaUrl);
}

export function getDirname(metaUrl) {
  return dirname(getFilename(metaUrl));
}

// import the zv1 engine locally
import zv1 from "../src/index.js";

/**
 * Flow Test Runner
 * 
 * Supports two test file formats:
 * 
 * 1. Legacy JSON format (embedded flow):
 *    - File: flow.combined-testing.json
 *    - Structure: { "flow": {...}, "inputs": {...}, "expected": {...} }
 * 
 * 2. New .zv1 format (separate test metadata):
 *    - File: flow.zv1-test.zv1 (the actual .zv1 file)
 *    - Metadata: flow.zv1-test.test.json (test configuration)
 *    - Structure: { "inputs": {...}, "expected": {...}, "expectedSchema": {...} }
 * 
 * The test runner automatically detects the format and loads accordingly.
 */

async function runFlowTest(testFile) {
  const testPath = path.join(getDirname(import.meta.url), "./flows", testFile);
  
  let testData, flow, inputs, expected, expectedSchema, expectedError;
  
  // Check if this is a .zv1 file with companion .test.json
  if (testFile.endsWith('.zv1')) {
    const testMetadataPath = testPath.replace('.zv1', '.test.json');
    
    if (!fs.existsSync(testMetadataPath)) {
      console.log(`[SKIP] No test metadata found for ${testFile}, skipping...`);
      return;
    }
    
    // Load test metadata
    testData = JSON.parse(fs.readFileSync(testMetadataPath, "utf-8"));
    flow = testPath; // Use the .zv1 file path directly
    inputs = testData.inputs;
    expected = testData.expected;
    expectedSchema = testData.expectedSchema;
    expectedError = testData.expectedError;
  } else {
    // Legacy JSON format with embedded flow
    testData = JSON.parse(fs.readFileSync(testPath, "utf-8"));
    flow = testData.flow;
    inputs = testData.inputs;
    expected = testData.expected;
    expectedSchema = testData.expectedSchema;
    expectedError = testData.expectedError;
  }

  console.log(`[INFO] Testing flow: ${testFile} with inputs: ${JSON.stringify(inputs)}`);
  const engine = await zv1.create(flow, { 
    debug: true,
    keys: {
      openrouter: process.env.OPENROUTER_API_KEY,
      google_custom_search: {
        key: process.env.GOOGLE_CUSTOM_SEARCH_KEY,
        cx: process.env.GOOGLE_CUSTOM_SEARCH_CX
      }
    }
  }); // Enable debug mode
  
  try {
    const result = await engine.run(inputs);
    console.log(`  [RESULT] ${JSON.stringify(result)}`);
    
    // If we expected an error but got success, that's a failure
    if (expectedError) {
      console.error(`  [FAIL] Expected error but flow succeeded for ${testFile}`);
      throw new Error(`Expected error but flow succeeded`);
    }
    
    if(expected){
      assert.deepStrictEqual(result.outputs, expected, `  [FAIL] Output mismatch for ${testFile}`);
    } else if(expectedSchema){
      // compare the result with the expected schema to see if it matches the overall shape but not the values
      const ajv = new Ajv();
      const validate = ajv.compile(expectedSchema);
      const valid = validate(result);
      if (!valid) {
        console.error(`  [FAIL] Output mismatch for ${testFile}`);
        console.error(`    Error: ${JSON.stringify(validate.errors, null, 2)}`);
        throw new Error(`  [FAIL] Output mismatch for ${testFile}`);
      }
    }
    console.log(`  [PASS] ${testFile}`);
  } catch (err) {
    // If we expected an error, check if it matches our expectations
    if (expectedError) {
      console.log(`  [EXPECTED ERROR] ${testFile}`);
      console.log(`    Error Type: ${err.errorType || 'Unknown'}`);
      console.log(`    Error Message: ${err.message}`);
      
      // Validate error details if specified
      if (expectedError.type && err.errorType !== expectedError.type) {
        console.error(`    [FAIL] Expected error type '${expectedError.type}' but got '${err.errorType}'`);
        throw new Error(`Error type mismatch: expected '${expectedError.type}' but got '${err.errorType}'`);
      }
      
      if (expectedError.message && !err.message.includes(expectedError.message)) {
        console.error(`    [FAIL] Expected error message to contain '${expectedError.message}' but got '${err.message}'`);
        throw new Error(`Error message mismatch: expected '${expectedError.message}' but got '${err.message}'`);
      }
      
      if (expectedError.nodeId && err.errorDetails?.nodeId !== expectedError.nodeId) {
        console.error(`    [FAIL] Expected error node ID '${expectedError.nodeId}' but got '${err.errorDetails?.nodeId}'`);
        throw new Error(`Error node ID mismatch: expected '${expectedError.nodeId}' but got '${err.errorDetails?.nodeId}'`);
      }
      
      if (expectedError.nodeType && err.errorDetails?.nodeType !== expectedError.nodeType) {
        console.error(`    [FAIL] Expected error node type '${expectedError.nodeType}' but got '${err.errorDetails?.nodeType}'`);
        throw new Error(`Error node type mismatch: expected '${expectedError.nodeType}' but got '${err.errorDetails?.nodeType}'`);
      }
      
      console.log(`    [PASS] Error matches expectations`);
      return; // Success for expected errors
    }
    
    // If we didn't expect an error, this is a failure
    console.log(err);
    console.error(`  [FAIL] ${testFile}`);
    console.error(`    Error: ${err.message}`);
    console.error(`    Stack Trace: ${err.stack}`);
    console.error(`    Flow: ${JSON.stringify(flow, null, 2)}`);
    console.error(`    Expected Output: ${JSON.stringify(expected, null, 2)}`);
    console.error(`    Actual Output: ${JSON.stringify(err.actual, null, 2)}`);
    throw err;
  }
}

async function runAllTests() {
  const testDir = path.join(getDirname(import.meta.url), "./flows");
  const allFiles = fs.readdirSync(testDir);
  
  // Get all test files: .json files (legacy) and .zv1 files (new format)
  // Skip .test.json files as they are metadata files, not flows
  const testFiles = allFiles.filter((file) => 
    (file.endsWith(".json") && !file.endsWith(".test.json")) || file.endsWith(".zv1")
  );

  let passed = 0;
  let failed = 0;

  for (const testFile of testFiles) {
    try {
      await runFlowTest(testFile);
      passed++;
    } catch (error) {
      console.error(`  [FAIL] ${error}`);
      throw error;
      failed++;
    }
  }

  console.log(`\n[INFO] Flow Test Suite Completed: ${passed} Passed, ${failed} Failed.`);
  if (failed > 0) {
    process.exit(1);
  }
}

async function runSingleTest(filename) {
  const testDir = path.join(getDirname(import.meta.url), "./flows");
  const testPath = path.join(testDir, filename);
  
  // Check if the file exists
  if (!fs.existsSync(testPath)) {
    console.error(`[ERROR] Test file not found: ${filename}`);
    console.error(`Available test files:`);
    const allFiles = fs.readdirSync(testDir);
    const testFiles = allFiles.filter((file) => 
      (file.endsWith(".json") && !file.endsWith(".test.json")) || file.endsWith(".zv1")
    );
    testFiles.forEach(file => console.error(`  - ${file}`));
    process.exit(1);
  }

  let passed = 0;
  let failed = 0;

  try {
    await runFlowTest(filename);
    passed++;
    console.log(`\n[INFO] Single Flow Test Completed: ${passed} Passed, ${failed} Failed.`);
  } catch (error) {
    console.error(`  [FAIL] ${error}`);
    failed++;
    console.log(`\n[INFO] Single Flow Test Completed: ${passed} Passed, ${failed} Failed.`);
    if (failed > 0) {
      process.exit(1);
    }
  }
}

// Parse command line arguments
const args = process.argv.slice(2);
const filename = args[0];

// Main execution logic
if (filename) {
  // Test a single flow file
  console.log(`[INFO] Running single flow test: ${filename}`);
  runSingleTest(filename).catch((err) => {
    console.error("[ERROR] Single flow test encountered an unexpected error.");
    console.error(err.stack);
    process.exit(1);
  });
} else {
  // Test all flows
  console.log(`[INFO] Running all flow tests`);
  runAllTests().catch((err) => {
    console.error("[ERROR] Flow test suite encountered an unexpected error.");
    console.error(err.stack);
    process.exit(1);
  });
}
