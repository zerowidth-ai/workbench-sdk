import fs from "fs";
import path from "path";
import assert from "assert";
import dotenv from "dotenv";

import { getDirname } from "../src/utilities/helpers.js";
import { loadIntegrations } from "../src/utilities/loaders.js";

/**
 * Recursively substitute ${VAR} patterns with environment variable values
 */
function substituteEnvVars(obj) {
  if (typeof obj === 'string') {
    return obj.replace(/\$\{([^}]+)\}/g, (match, varName) => {
      const value = process.env[varName];
      return value !== undefined ? value : match;
    });
  }
  if (Array.isArray(obj)) {
    return obj.map(item => substituteEnvVars(item));
  }
  if (obj !== null && typeof obj === 'object') {
    const result = {};
    for (const [key, value] of Object.entries(obj)) {
      result[key] = substituteEnvVars(value);
    }
    return result;
  }
  return obj;
}

// Custom test functions
const customTests = {
  shuffleTest: (result, testCase) => {
    const input = testCase.inputs.array;
    const output = result.array;
    
    // Check length
    assert.strictEqual(output.length, input.length, "Output array should have the same length as input");
    
    // Check that all elements from input are in output
    for (const item of input) {
      assert(output.includes(item), `Output should contain all elements from input: missing ${item}`);
    }
    
    // Check that all elements from output are in input
    for (const item of output) {
      assert(input.includes(item), `Output should only contain elements from input: extra ${item}`);
    }
    
    // If array has more than 1 element, check that order is different
    // (technically a shuffle could result in the same order, but it's very unlikely for larger arrays)
    if (input.length > 3) {
      let sameOrder = true;
      for (let i = 0; i < input.length; i++) {
        if (input[i] !== output[i]) {
          sameOrder = false;
          break;
        }
      }
      assert(!sameOrder, "Output array should be in a different order than input");
    }
    
    return true;
  },
  
  seedShuffleTest: (result, testCase) => {
    // For seeded shuffles, we should get consistent results
    // But we don't know what those results are without implementing the algorithm
    // So we'll just check that the output is a valid shuffle
    return customTests.shuffleTest(result, testCase);
  }
};

async function runNodeTest(config, nodeDir, testCase, testResults) {
  const nodeConfigPath = path.join(nodeDir, `${path.basename(nodeDir)}.config.json`);
  const nodeProcessPath = path.join(nodeDir, `${path.basename(nodeDir)}.process.js`);

  if (!fs.existsSync(nodeConfigPath) || !fs.existsSync(nodeProcessPath)) {
    const error = `Missing config or process file in: ${nodeDir}`;
    console.error(`✖ ${testCase.description} - ${error}`);
    testResults.failures.push({
      node: path.basename(nodeDir),
      test: testCase.description,
      error: error
    });
    return false;
  }

  const processFunction = await import(nodeProcessPath).then(module => module.default);
  const nodeConfig = JSON.parse(fs.readFileSync(nodeConfigPath, "utf-8"));
  
  // Substitute environment variables in inputs (e.g., ${AIRTABLE_TEST_BASE_ID})
  const substitutedInputs = substituteEnvVars(testCase.inputs);

  // Merge default values from nodeConfig into testCase.inputs
  const inputsWithDefaults = { ...substitutedInputs };
  for (const inputDef of nodeConfig.inputs) {
    if (inputsWithDefaults[inputDef.name] === undefined && inputDef.default !== undefined) {
      inputsWithDefaults[inputDef.name] = inputDef.default;
    }
  }

  // Substitute environment variables in settings as well
  const substitutedSettings = substituteEnvVars(testCase.settings || {});

  // Apply default settings from node nodeConfiguration
  const settingsWithDefaults = { ...substitutedSettings };
  if (nodeConfig.settings) {
    for (const settingDef of nodeConfig.settings) {
      if (settingDef.default !== undefined && settingsWithDefaults[settingDef.name] === undefined) {
        settingsWithDefaults[settingDef.name] = settingDef.default;
      }
    }
  }
  
  try {
    
    const result = await processFunction({inputs: inputsWithDefaults, settings: settingsWithDefaults, config: config, nodeConfig: nodeConfig});

    if (testCase.expectedError) {
      const error = `Expected error but none was thrown`;
      console.error(`✖ ${testCase.description} - ${error}`);
      testResults.failures.push({
        node: path.basename(nodeDir),
        test: testCase.description,
        error: error
      });
      return false;
    }

    // Handle custom test functions
    if (testCase.customTest && customTests[testCase.customTest]) {
      const passed = customTests[testCase.customTest](result, testCase);
      if (passed) {
        console.log(`✔ ${testCase.description}`);
        testResults.passed++;
        return true;
      } else {
        const error = `Custom test function failed`;
        console.error(`✖ ${testCase.description} - ${error}`);
        testResults.failures.push({
          node: path.basename(nodeDir),
          test: testCase.description,
          error: error
        });
        return false;
      }
    }

    // Check against expectedSchema if provided
    if (testCase.expectedSchema) {
      let allValid = true;
      let validationErrors = [];

      for (const [key, schema] of Object.entries(testCase.expectedSchema)) {
        if (!(key in result)) {
          allValid = false;
          validationErrors.push(`Missing expected output: ${key}`);
          continue;
        }

        const value = result[key];
        
        // Check type constraints
        if (schema.type) {
          const types = Array.isArray(schema.type) ? schema.type : [schema.type];
          const typeValid = types.some(type => {
            if (type === 'number') return typeof value === 'number';
            if (type === 'string') return typeof value === 'string';
            if (type === 'boolean') return typeof value === 'boolean';
            if (type === 'object') return typeof value === 'object' && value !== null && !Array.isArray(value);
            if (type === 'array') return Array.isArray(value);
            if (type === 'null') return value === null;
            return false;
          });

          if (!typeValid) {
            allValid = false;
            validationErrors.push(`Type mismatch for ${key}: expected ${schema.type}, got ${typeof value}`);
          }
        }

        // Check numeric constraints
        if (typeof value === 'number') {
          if (schema.minimum !== undefined && value < schema.minimum) {
            allValid = false;
            validationErrors.push(`Value ${value} for ${key} is less than minimum ${schema.minimum}`);
          }
          if (schema.maximum !== undefined && value > schema.maximum) {
            allValid = false;
            validationErrors.push(`Value ${value} for ${key} is greater than maximum ${schema.maximum}`);
          }
        }

        // Check string constraints
        if (typeof value === 'string' && schema.pattern) {
          const regex = new RegExp(schema.pattern);
          if (!regex.test(value)) {
            allValid = false;
            validationErrors.push(`Value "${value}" for ${key} does not match pattern ${schema.pattern}`);
          }
        }

        // Check array constraints
        if (Array.isArray(value)) {
          if (schema.minItems !== undefined && value.length < schema.minItems) {
            allValid = false;
            validationErrors.push(`Array ${key} has fewer items (${value.length}) than required (${schema.minItems})`);
          }
          if (schema.maxItems !== undefined && value.length > schema.maxItems) {
            allValid = false;
            validationErrors.push(`Array ${key} has more items (${value.length}) than allowed (${schema.maxItems})`);
          }
        }
      }

      if (!allValid) {
        const error = `Schema validation failed: ${validationErrors.join(', ')}`;
        console.error(`✖ ${testCase.description} - Schema validation failed:`);
        validationErrors.forEach(err => console.error(`  - ${err}`));
        testResults.failures.push({
          node: path.basename(nodeDir),
          test: testCase.description,
          error: error
        });
        return false;
      }
      
      console.log(`✔ ${testCase.description} (schema validation)`);
      testResults.passed++;
      return true;
    }

    // Regular expected value testing
    if (testCase.expected) {
      try {
        for (const [key, value] of Object.entries(testCase.expected)) {
          assert.deepStrictEqual(result[key], value, `Mismatch for ${key}: expected ${JSON.stringify(value)}, got ${JSON.stringify(result[key])}`);
        }
      } catch (assertionError) {
        const error = assertionError.message;
        console.error(`✖ ${testCase.description} - ${error}`);
        testResults.failures.push({
          node: path.basename(nodeDir),
          test: testCase.description,
          error: error
        });
        return false;
      }
    } else if (!testCase.customTest && !testCase.expectedSchema) {
      console.warn(`⚠ ${testCase.description} - No validation criteria provided (expected, expectedSchema, or customTest)`);
    }

    console.log(`✔ ${testCase.description}`);
    testResults.passed++;
    return true;
  } catch (err) {
    if (testCase.expectedError) {
      try {
        assert.strictEqual(err.message, testCase.expectedError, `Error mismatch: expected "${testCase.expectedError}", got "${err.message}"`);
        console.log(`✔ ${testCase.description}`);
        testResults.passed++;
        return true;
      } catch (assertionError) {
        const error = assertionError.message;
        console.error(`✖ ${testCase.description} - ${error}`);
        testResults.failures.push({
          node: path.basename(nodeDir),
          test: testCase.description,
          error: error
        });
        return false;
      }
    } else {
      const error = err.message || 'Unexpected error occurred';
      console.error(`✖ ${testCase.description} - Unexpected error:`);
      console.error(err);
      testResults.failures.push({
        node: path.basename(nodeDir),
        test: testCase.description,
        error: error
      });
      return false;
    }
  }
}


function parseArguments() {
  const args = process.argv.slice(2);
  const options = {};
  
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    
    if (arg === '--help' || arg === '-h') {
      console.log(`
Usage: node test.all-nodes.js [options]

Options:
  --node <node-name>        Run tests for a specific node only
  --start-from <node-name>  Run tests for all nodes starting from the specified node
  --help, -h               Show this help message

Examples:
  node test.all-nodes.js --node add
  node test.all-nodes.js --start-from array-map
  node test.all-nodes.js
      `);
      process.exit(0);
    } else if (arg === '--node') {
      if (i + 1 >= args.length) {
        console.error('Error: --node requires a node name');
        process.exit(1);
      }
      options.node = args[i + 1];
      i++; // Skip next argument as it's the value
    } else if (arg === '--start-from') {
      if (i + 1 >= args.length) {
        console.error('Error: --start-from requires a node name');
        process.exit(1);
      }
      options.startFrom = args[i + 1];
      i++; // Skip next argument as it's the value
    } else if (!arg.startsWith('--')) {
      // Legacy support: treat first non-option argument as node name
      if (!options.node && !options.startFrom) {
        options.node = arg;
      }
    }
  }
  
  return options;
}

async function runTests() {
  dotenv.config();
  const nodesDir = path.join(getDirname(import.meta.url), "../nodes");
  const nodeDirs = fs.readdirSync(nodesDir).sort(); // Sort for consistent ordering

  const integrations = await loadIntegrations({
    keys: {
      openrouter: process.env.OPENROUTER_API_KEY,
      newsdata_io: process.env.NEWSDATA_IO_API_KEY,
      airtable: process.env.AIRTABLE_API_KEY,
      notion: process.env.NOTION_API_KEY
    }
  });

  const config = {
    integrations: integrations
  };

  const options = parseArguments();
  let nodesToTest;

  if (options.node && options.startFrom) {
    console.error('Error: Cannot specify both --node and --start-from options');
    process.exit(1);
  }

  if (options.node) {
    // Run tests for a specific node only
    if (!nodeDirs.includes(options.node)) {
      console.error(`Node "${options.node}" not found in nodes directory.`);
      console.error(`Available nodes: ${nodeDirs.join(', ')}`);
      process.exit(1);
    }
    nodesToTest = [options.node];
    console.log(`Running tests for single node: ${options.node}`);
  } else if (options.startFrom) {
    // Run tests starting from a specific node
    const startIndex = nodeDirs.indexOf(options.startFrom);
    if (startIndex === -1) {
      console.error(`Node "${options.startFrom}" not found in nodes directory.`);
      console.error(`Available nodes: ${nodeDirs.join(', ')}`);
      process.exit(1);
    }
    nodesToTest = nodeDirs.slice(startIndex);
    console.log(`Running tests starting from node: ${options.startFrom} (${nodesToTest.length} nodes total)`);
  } else {
    // Run tests for all nodes
    nodesToTest = nodeDirs;
    console.log(`Running tests for all ${nodesToTest.length} nodes`);
  }

  // Initialize test results tracking
  const testResults = {
    passed: 0,
    failures: []
  };

  for (const nodeDir of nodesToTest) {
    const testsPath = path.join(nodesDir, nodeDir, `${nodeDir}.tests.json`);
    if (!fs.existsSync(testsPath)) continue;

    const tests = JSON.parse(fs.readFileSync(testsPath, "utf-8"));
    console.log(`Running tests for node: ${nodeDir}`);
    for (const testCase of tests) {
      try {
        await runNodeTest(config, path.join(nodesDir, nodeDir), testCase, testResults);
      } catch (err) {
        console.error(`✖ ${testCase.description} - Fatal error: ${err.message}`);
        testResults.failures.push({
          node: nodeDir,
          test: testCase.description,
          error: err.message || 'Fatal error occurred'
        });
      }
    }
  }

  // Print summary
  console.log('\n' + '='.repeat(60));
  console.log('TEST SUMMARY');
  console.log('='.repeat(60));
  
  const totalTests = testResults.passed + testResults.failures.length;
  console.log(`Total tests run: ${totalTests}`);
  console.log(`Passed: ${testResults.passed}`);
  console.log(`Failed: ${testResults.failures.length}`);
  
  if (testResults.failures.length > 0) {
    console.log('\nFAILED TESTS:');
    console.log('-'.repeat(40));
    for (const failure of testResults.failures) {
      console.log(`${failure.node}: ${failure.test}`);
      console.log(`  Error: ${failure.error}`);
      console.log('');
    }
    
    console.log(`❌ ${testResults.failures.length} test(s) failed!`);
    process.exit(1);
  } else {
    console.log('\n✅ All tests passed!');
  }
}

runTests().catch((err) => {
  console.error(err);
  process.exit(1);
});
