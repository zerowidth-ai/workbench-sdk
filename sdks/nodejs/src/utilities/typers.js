import path from "path";
import fs from "fs";
import Ajv from "ajv";
import zv1 from "../index.js";

import { getDirname } from "./helpers.js";

const ajv = new Ajv();

/**
 * Load custom type configurations from ./types/<type>.json
 * @returns {Promise<Object>} Map of type names to compiled validators
 */
export async function loadCustomTypes() {
  const retval = {};
  
  const typeDir = path.join(getDirname(import.meta.url), "../types");


  if (fs.existsSync(typeDir)) {
    const typeFiles = fs.readdirSync(typeDir);

    await Promise.all(typeFiles.map(async (typeFile) => {
      const typePath = path.join(typeDir, typeFile);
      const typeName = typeFile.replace(/\.json$/, "");

      try {
        const type = await import(typePath, { with: { type: "json" } });

        // For each custom type, compile the schema
        retval[typeName] = ajv.compile(type);

      } catch (err) { 
        console.error(err);
      }
    }));
  } else {
    throw new Error("No types directory found, skipping custom type loading");
  }

  return retval;
}


/**
 * Check if a value matches a given type
 * Handles basic types, custom types, and type unions
 * @param {any} value - The value to check
 * @param {string} type - The expected type
 * @returns {boolean} Whether the value matches the type
 */
export function typeCheck(value, type) {
  this.logDebug(`Type checking value against type '${type}'`, value);
  
  if (value === null) {
    this.logDebug("Null value passes type check");
    return true;
  }
  
  type = type.toLowerCase().trim();

  if (type === "any") {
    this.logDebug("'any' type always passes");
    return true;
  }

  if (type.includes(" or ")) {
    const typeOptions = type.split(" or ");
    this.logDebug(`Union type with options: ${typeOptions.join(', ')}`);
    return typeOptions.some((t) => this.typeCheck(value, t.trim()));
  }

  if (type === "number" && typeof value === "string") {
    const isNumeric = !isNaN(value);
    this.logDebug(`String to number conversion check: ${isNumeric ? "passed" : "failed"}`);
    return isNumeric;
  }

  if (type === "array") {
    const isArray = Array.isArray(value);
    this.logDebug(`Array type check: ${isArray ? "passed" : "failed"}`);
    return isArray;
  }

  if (type.startsWith("array of ")) {
    if (!Array.isArray(value)) {
      this.logDebug("Failed array check for 'array of' type");
      return false;
    }
    
    const itemType = type.slice(9).replace(/s$/, "");
    this.logDebug(`Checking each item in array against type: ${itemType}`);
    return value.every((item, index) => {
      const itemResult = this.typeCheck(item, itemType);
      if (!itemResult) {
        this.logDebug(`Item at index ${index} failed type check`);
      }
      return itemResult;
    });
  }

  if (this.compiledCustomTypes[type]) {
    const customTypeResult = this.compiledCustomTypes[type](value);
    this.logDebug(`Custom type '${type}' validation: ${customTypeResult ? "passed" : "failed"}`);
    return customTypeResult;
  }

  const typeResult = typeof value === type;
  this.logDebug(`Basic type check (${typeof value} === ${type}): ${typeResult ? "passed" : "failed"}`);
  return typeResult;
}


/**
 * Convert an import definition into a node type configuration
 * @private
 */
export function convertImportToNodeType(importDef) {
  this.logDebug(`Converting import ${importDef.id} to node type`);

  // First ensure any nested imports are processed
  let processedImportDef = { ...importDef };
  if (importDef.imports && importDef.imports.length > 0) {
    this.logDebug(`Processing ${importDef.imports.length} nested imports`);
    
    // Load nested imports as node types
    const nestedNodes = [];
    for (const nestedImport of importDef.imports) {
      const nodeType = this.convertImportToNodeType(nestedImport);
      nestedNodes.push(nodeType);
    }

    // Add the nested import nodes to the flow
    processedImportDef.nodes = [...processedImportDef.nodes, ...nestedNodes];
  }
  processedImportDef.nodes = processedImportDef.nodes.filter(node => !node.debug_only);

  // Rest of the existing code...
  const inputNodes = processedImportDef.nodes.filter(node => 
    node.type === 'input-chat' || 
    node.type === 'input-prompt' || 
    node.type === 'input-data'
  );
  
  const outputNodes = processedImportDef.nodes.filter(node => 
    node.type === 'output-chat' || 
    node.type === 'output-data'
  );

  this.logDebug(`Found ${inputNodes.length} input nodes and ${outputNodes.length} output nodes`);

  return {
    config: {
      display_name: processedImportDef.display_name || "Imported Flow",
      description: processedImportDef.description || "An imported flow",
      category: "imported",
      is_constant: true, // All imports are potentially constant
      is_plugin: true,   // <-- Add this line to mark all imports as plugin-capable
      is_import: true,
      accepts_plugins: processedImportDef.nodes.some(node => node.type === 'input-plugins'),
      // Store import metadata for reference
      importId: processedImportDef.importId,
      requestedSnapshot: processedImportDef.requestedSnapshot,
      inputs: inputNodes.map(node => {
        if (node.type === 'input-data') {
          return {
            // Use the node's settings.key as the input name to match port connections
            name: node.settings?.key || 'data',
            display_name: `Data: ${node.settings?.key || 'value'}`,
            type: node.settings?.type || 'any',
            required: true,
            is_data_input: true,
            description: node.settings?.description || 'Imported data input'
          };
        } else if (node.type === 'input-chat') {
          return {
            // Use the node's settings.key as the input name to match port connections
            name: node.settings?.key || 'chat',
            display_name: 'Chat',
            type: 'array of messages',
            required: true,
            is_chat_input: true,
            description: 'Chat messages to process'
          };
        } else { // input-prompt
          return {
            // Use the node's settings.key as the input name to match port connections
            name: node.settings?.key || 'prompt',
            display_name: 'Prompt',
            type: 'string',
            required: true,
            is_prompt_input: true,
            description: 'Prompt input'
          };
        }
      }),

      outputs: outputNodes.map(node => {
        if (node.type === 'output-data') {
          return {
            // name: node.id,
            name: node.settings?.key || 'data',
            display_name: `Data: ${node.settings?.key || 'value'}`,
            type: node.settings?.type || 'any',
            description: node.settings?.description || 'Imported data output'
          };
        } else { // output-chat
          return {
            // name: node.id,
            name: node.settings?.key || 'chat',
            display_name: 'Response',
            type: 'message',
            description: 'Chat response output'
          };
        }
      }),

      // Store the full import definition for use during processing
      importDefinition: processedImportDef
    },

    // All imports share this process function
    process: async ({inputs, settings, config, nodeConfig}) => {
      this.logDebug(`Processing import node with inputs:`, inputs);
      
      const timelineEntry = {
        nodeId: processedImportDef.id,
        nodeType: 'import',
        inputs: JSON.parse(JSON.stringify(inputs)),
        settings: JSON.parse(JSON.stringify(settings)),
        startTime: new Date().toISOString()
      };
      const startDate = new Date();

      // Create a new engine instance with the processed import definition
      // If the import has a knowledge database, add it to the config
      let importConfig = { ...config };
      if (processedImportDef.knowledgeDbPath) {
        // Create SQLite integration for this import's knowledge database
        const SQLiteIntegration = (await import('../integrations/sqlite.js')).default;
        const sqliteIntegration = new SQLiteIntegration(processedImportDef.knowledgeDbPath, {
          timeout: config.sqliteTimeout || 5000
        });
        
        // Add to integrations
        importConfig.integrations = {
          ...config.integrations,
          sqlite: sqliteIntegration
        };
        
        this.logDebug(`[INFO] Created SQLite integration for import ${processedImportDef.id} with knowledge database:`, processedImportDef.knowledgeDbPath);
      }
      
      // If this import accepts plugins, create tool runners for parent context execution
      // Note: We need to access the parent engine (this) to find connected plugins
      let tools = {};
      if (nodeConfig.accepts_plugins && this.flow && this.flow.links) {
        this.logDebug(`Import [${nodeConfig.id}] accepts plugins, creating tool runners for parent context execution`);
        
        // Find the current node in the parent flow to get its plugin connections
        const currentNode = this.flow.nodes.find(n => n.type === nodeConfig.id || n.type === `imported-${nodeConfig.id}`);
        
        if (currentNode) {
          // Find all plugin nodes connected to this import in the parent flow
          const externalPluginNodeIds = this.flow.links
            .filter(link => link.type === "plugin" && link.to.node_id === currentNode.id)
            .map(link => link.from.node_id);
          
          this.logDebug(`Found ${externalPluginNodeIds.length} external plugins connected to import [${currentNode.id}]`);
          
          // Create tool definitions for each external plugin
          for (const externalPluginNodeId of externalPluginNodeIds) {
            const externalPluginNode = this.flow.nodes.find(n => n.id === externalPluginNodeId);
            if (externalPluginNode) {
              // Generate the tool schema from the parent context
              const schema = this.generateToolSchema(externalPluginNode);
              
              // Create a tool runner that executes in PARENT context
              const toolRunner = async (args) => {
                this.logDebug(`Tool runner called for [${schema.name}] from internal import engine`);
                return await this.executePluginInParentContext(externalPluginNode, args);
              };
              
              tools[schema.name] = {
                schema: schema,
                process: toolRunner
              };
              
              this.logDebug(`Created tool runner for plugin [${externalPluginNode.id}] -> [${schema.name}]`);
            }
          }
        }
      }
      
      // Add tools to import config if any were created
      if (Object.keys(tools).length > 0) {
        importConfig.tools = tools;
      }
      
      const importEngine = await zv1.create(processedImportDef, importConfig);
      
      // Share executed states with import engine to prevent duplicate execution
      importEngine.executedNodeStates = this.executedNodeStates;

      // Map input port names to the data keys that the imported flow expects
      const inputData = {};
      const inputNodes = processedImportDef.nodes.filter(node => 
        node.type === 'input-data' || node.type === 'input-chat' || node.type === 'input-prompt'
      );
      
      this.logDebug(`Import node inputs received:`, inputs);
      this.logDebug(`Import flow input nodes:`, inputNodes.map(n => ({ id: n.id, type: n.type, key: n.settings?.key })));
      
      for (const inputNode of inputNodes) {
        const dataKey = inputNode.settings?.key || (inputNode.type === 'input-data' ? 'data' : 
                                                    inputNode.type === 'input-chat' ? 'chat' : 'prompt');
        this.logDebug(`Mapping input port '${dataKey}' to data key '${dataKey}'`);
        if (inputs[dataKey] !== undefined) {
          inputData[dataKey] = inputs[dataKey];
          this.logDebug(`Mapped input '${dataKey}':`, inputs[dataKey]);
        } else {
          this.logDebug(`No input found for port '${dataKey}'`);
        }
      }
      
      this.logDebug(`Final input data for imported flow:`, inputData);

      // Run the imported flow
      const result = await importEngine.run(inputData);

      // cleanup the import engine
      await importEngine.cleanup();

      const endDate = new Date();
      if(result.outputs) {
        timelineEntry.outputs = JSON.parse(JSON.stringify(result.outputs));
      } else {
        timelineEntry.outputs = {};
      }
      if(result.terminalNodes) {
        timelineEntry.terminalNodes = JSON.parse(JSON.stringify(result.terminalNodes));
      } else {
        timelineEntry.terminalNodes = [];
      }
      timelineEntry.endTime = endDate.toISOString();
      timelineEntry.durationMs = endDate - startDate;
      this.timeline.push(timelineEntry);
      this.logDebug(`Import node execution result:`, result.outputs);

      // Map outputs back to the outer flow's format
      const outputs = result.outputs || {};

      // --- Handle terminal nodes from the imported flow ---
      if (result.terminalNodes && Array.isArray(result.terminalNodes)) {
        this.logDebug(`Processing ${result.terminalNodes.length} terminal nodes from imported flow`);
        
        // Create a mapping of terminal node IDs to their expected output port names
        // by looking at the original flow's output nodes and their settings
        const terminalNodeOutputMapping = {};
        const originalOutputNodes = processedImportDef.nodes.filter(node => 
          (node.type === 'output-data' || node.type === 'output-chat') && !node.debug_only
        );
        
        // For each original output node, map it to the terminal node that should provide its data
        for (const outputNode of originalOutputNodes) {
          const outputKey = outputNode.settings?.key || (outputNode.type === 'output-data' ? 'data' : 'chat');
          // Find which terminal node this output node was connected to
          const outputLinks = processedImportDef.links.filter(link => link.to.node_id === outputNode.id);
          for (const link of outputLinks) {
            const sourceNodeId = link.from.node_id;
            if (!terminalNodeOutputMapping[sourceNodeId]) {
              terminalNodeOutputMapping[sourceNodeId] = {};
            }
            terminalNodeOutputMapping[sourceNodeId][link.from.port_name] = outputKey;
          }
        }
        
        this.logDebug(`Terminal node output mapping:`, terminalNodeOutputMapping);
        
        for (const terminalNode of result.terminalNodes) {
          if (terminalNode.outputs) {
            const nodeMapping = terminalNodeOutputMapping[terminalNode.node_id] || {};
            for (const [outputName, outputValue] of Object.entries(terminalNode.outputs)) {
              // Use the mapped output key if available, otherwise fall back to the original name
              const mappedKey = nodeMapping[outputName] || outputName;
              // Use the full node ID prefix format that the parent flow expects
              // The node ID format should be: imported-{flowId}-{nodeId}_{outputKey}
              const fullKey = `imported-${processedImportDef.id}-${terminalNode.node_id}_${mappedKey}`;
              outputs[fullKey] = outputValue;
              this.logDebug(`Added terminal output: ${fullKey} = ${JSON.stringify(outputValue)} (from ${terminalNode.node_id}:${outputName})`);
            }
          }
        }
      } else {
        // Fallback: Add outputs for all terminal nodes in the imported flow using cache
        const nodesWithOutgoingLinks = new Set(processedImportDef.links.map(link => link.from.node_id));
        const terminalNodes = processedImportDef.nodes.filter(node => !nodesWithOutgoingLinks.has(node.id));
        for (const terminalNode of terminalNodes) {
          if (terminalNode.type === 'output-data' || terminalNode.type === 'output-chat') continue;
          // Look up config for this node type
          const nodeConfig = this.nodes[terminalNode.type]?.config;
          if (!nodeConfig || !Array.isArray(nodeConfig.outputs)) continue;
          for (const output of nodeConfig.outputs) {
            const key = `${terminalNode.id}_${output.name}`;
            const cacheKey = `${terminalNode.id}:${output.name}`;
            const value = importEngine.cache[cacheKey];
            if (value !== undefined) {
              outputs[key] = value;
            }
          }
        }
      }

      return outputs;
    }
  };
}