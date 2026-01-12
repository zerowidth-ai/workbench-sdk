import fs from "fs";
import path from "path";
import Ajv from "ajv";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";
import crypto from "crypto";

import ErrorManager from "./classes/ErrorManager.js";
import CacheManager from "./utilities/cache.js";

import { callMCPTool, fetchMCPToolSchema } from "./utilities/mcp.js";
import { loadNodes, loadIntegrations, detectAndLoadFlow } from "./utilities/loaders.js";
import { validateKeys, validateFlow, validateInputs } from "./utilities/validators.js";
import { loadCustomTypes, typeCheck, convertType } from "./utilities/typers.js";
import { createSafeToolName, isRemoteMCPTool, isManualToolNode, mapTypeToJSONSchema, getDirname } from "./utilities/helpers.js";


/**
 * zv1 - Core class for executing node-based flows
 * Handles node loading, input/output validation, and flow execution
 */
export default class zv1 {



  /**
   * Create a new zv1 instance
   * @param {Object} flow - The flow definition containing nodes and links  
   * @param {Object} config - Configuration options and context for the engine
   */
  constructor(flow, config = {}) {
    this.flow = flow;
    this.debug = true ; //config.debug || false;
    this.keys = config.keys || {};
    this.executionQueue = [];
    this.runningNodes = new Set();
    this.completedNodes = new Set();
    this.maxConcurrency = config.maxConcurrency || 5;
    this.lastError = null;

    this.maxPluginCalls = config.maxPluginCalls || 10;
    
    this.config = {
        ...config
    };

    // Track knowledge base files that need cleanup
    this.knowledgeFilesToCleanup = new Set();
    
    // Initialize timeout flag
    this.hasTimedOut = false;
    
    // Track executed node states to prevent duplicate processing
    this.executedNodeStates = new Set();
    
    // Track node hashes that are currently in the queue or running
    // This prevents adding the same node multiple times to the queue
    this.queuedNodeHashes = new Set();

  }
    
  async initialize() {

    this.loadNodes = loadNodes.bind(this);
    this.loadIntegrations = loadIntegrations.bind(this);
    this.loadCustomTypes = loadCustomTypes.bind(this);
    
    this.typeCheck = typeCheck.bind(this);
    this.convertType = convertType.bind(this);
    this.fetchMCPToolSchema = fetchMCPToolSchema.bind(this);
    this.validateKeys = validateKeys.bind(this);
    this.validateFlow = validateFlow.bind(this);
    this.validateInputs = validateInputs.bind(this);  


    const nodes = await this.loadNodes(this.flow);
    const compiledCustomTypes = await this.loadCustomTypes();

    if(!this.config.integrations) {
      this.config.integrations = await this.loadIntegrations(this.config, this.flow);
    }

    this.nodes = nodes;
    this.compiledCustomTypes = compiledCustomTypes;
    this.nodesDir = path.join(getDirname(import.meta.url), "../nodes");
    

    this.cache = new CacheManager();
    this.flowTimeout = null;
    this.timeline = [];

    // Initialize ErrorManager for centralized error handling
    this.errorManager = new ErrorManager({
      onError: this.config.onError || null,
      executionId: this.config.executionId || uuidv4(),
      executionContext: {
        timeline: this.timeline,
        nodeCount: this.flow.nodes.length
      }
    });

    // this.logDebug("zv1 initialized with config:", JSON.stringify(config, null, 2));
    this.logDebug(`Loaded ${Object.keys(nodes).length} node types`);
    this.logDebug(`Loaded ${Object.keys(compiledCustomTypes).length} custom types`);

    // Clean up the flow
    this.sanitizeFlow();

    // Validate keys for nodes
    this.validateKeys();

    // Ensure the flow can even be run (use expanded flow)
    this.validateFlow(this.flow);
    this.initializePluginMappings();

    // Track knowledge base files for cleanup
    this._trackKnowledgeFiles();
  }

  /**
   * Create a new zv1 instance
   * Supports both legacy JSON files and new .zv1 files with hierarchical imports
   * 
   * @param {string|Object} flow - File path (string) or flow definition object
   * @param {Object} config - Configuration options and context for the engine
   * @returns {Promise<zv1>} Fully initialized zv1 instance
   * @throws {Error} If flow cannot be loaded or is invalid
   * 
   * @example
   * // Load from .zv1 file
   * const engine = await zv1.create('./myflow.zv1', { keys: { openrouter: 'sk-...' } });
   * 
   * // Load from legacy JSON file
   * const engine = await zv1.create('./legacy.json', { keys: { openrouter: 'sk-...' } });
   * 
   * // Load from flow object
   * const engine = await zv1.create(flowObject, { keys: { openrouter: 'sk-...' } });
   */
  static async create(flow, config = {}) {
    try {
      // Use the new unified loader to detect and load the flow
      // This handles both legacy JSON files and new .zv1 files
      const loadedFlow = await detectAndLoadFlow(flow);
      
      // Create engine instance with the loaded flow
      const engine = new zv1(loadedFlow, config);

      // Initialize the engine (loads nodes, validates flow, etc.)
      await engine.initialize();
      
      return engine;
    } catch (error) {
      console.error(error);
      // Provide more context for common errors
      if (error.message.includes('not found')) {
        throw new Error(`Flow file not found: ${error.message}`);
      } else if (error.message.includes('Invalid JSON')) {
        throw new Error(`Invalid JSON in flow file: ${error.message}`);
      } else if (error.message.includes('Missing required')) {
        throw new Error(`Invalid flow structure: ${error.message}`);
      } else {
        throw new Error(`Failed to create zv1 instance: ${error.message}`);
      }
    }
  }

  /**
   * Helper function to log debug information
   * @param {...any} args - Arguments to log
   */
  logDebug(...args) {
    if (this.debug) {
      console.log("[DEBUG]", ...args);
    }
  }

  /**
   * Create a hash of node execution state (id + inputs + settings)
   * Used to prevent duplicate processing of nodes with identical contexts
   * @private
   * @param {string} nodeId - The node ID
   * @param {Object} inputs - The inputs object
   * @param {Object} settings - The settings object
   * @returns {string} SHA-256 hash of the execution state
   */
  /**
   * Helper to check if node has any refiring inputs
   * @private
   */
  _hasRefiringInput(nodeId) {
    const node = this.flow.nodes.find(n => n.id === nodeId);
    if (!node) return false;
    
    const nodeDefinition = this.nodes[node.type];
    if (!nodeDefinition) return false;

    return nodeDefinition.config.inputs.some(input => 
      input.allow_multiple && input.refires
    );
  }

  _createExecutionHash(nodeId, inputs, settings) {
    const state = {
      id: nodeId,
      inputs: inputs || {},
      settings: settings || {}
    };
    
    // For refiring nodes, add a timestamp based on the input values
    if (this._hasRefiringInput(nodeId)) {
      // Find the latest timestamp from any refiring input
      let latestInputTimestamp = 0;
      const node = this.flow.nodes.find(n => n.id === nodeId);
      const nodeDefinition = this.nodes[node.type];
      
      if (nodeDefinition?.config?.inputs) {
        nodeDefinition.config.inputs.forEach(inputDef => {
          if (inputDef.allow_multiple && inputDef.refires) {
            const inputLinks = this.flow.links.filter(
              link => link.to.node_id === nodeId && link.to.port_name === inputDef.name
            );
            
            inputLinks.forEach(link => {
              const timestamp = this.cache.getLatestTimestamp({
                node_id: link.from.node_id,
                port_name: link.from.port_name
              });
              if (timestamp && timestamp > latestInputTimestamp) {
                latestInputTimestamp = timestamp;
              }
            });
          }
        });
      }
      
      state.timestamp = latestInputTimestamp;
    } else {
      // For non-refiring nodes, include input values AND current timestamp
      // This ensures nodes re-execute when inputs change OR when called again
      state.inputHash = JSON.stringify(inputs || {});
      // state.timestamp = Number(process.hrtime.bigint()); // Current execution timestamp
    }
    
    // Create deterministic JSON string (sort keys for consistency)
    const stateString = JSON.stringify(state, Object.keys(state).sort());
    
    // Use SHA-256 hash
    return crypto.createHash('sha256')
      .update(stateString)
      .digest('hex')
      .substring(0, 16); // Use first 16 chars for shorter hash
  }

  /**
   * Update execution context for ErrorManager
   * @param {Object} context - Additional execution context
   */
  updateErrorContext(context) {
    if (this.errorManager) {
      this.errorManager.updateExecutionContext(context);
    }
  }

  /**
   * Core execution logic shared between processNode and processNodeWithArgs
   * @private
   */
  async _executeNodeCore(node, inputs, settings, nodeDefinition) {
    const timelineEntry = {
      nodeId: node.id,
      nodeType: node.type,
      inputs: JSON.parse(JSON.stringify(inputs)),
      settings: JSON.parse(JSON.stringify(settings || {})),
      startTime: new Date().toISOString()
    };
    const startDate = new Date();
    
    try {
      if(this.config.onNodeStart) {
        await this.config.onNodeStart({
          nodeId: node.id,
          nodeType: node.type,
          timestamp: Date.now(),
          inputs: inputs,
          settings: settings || {}
        });
      }

      // add type and id to nodeConfig
      nodeDefinition.config.type = node.type;
      nodeDefinition.config.id = node.id;

      const outputs = await nodeDefinition.process({inputs, settings, config: this.config, nodeConfig: nodeDefinition.config});
      const endDate = new Date();
      timelineEntry.outputs = JSON.parse(JSON.stringify(outputs));
      timelineEntry.endTime = endDate.toISOString();
      timelineEntry.durationMs = endDate - startDate;
      timelineEntry.status = 'success';
      this.timeline.push(timelineEntry);
      
      if(this.config.onNodeComplete) {
        await this.config.onNodeComplete({
          nodeId: node.id,
          nodeType: node.type,
          timestamp: Date.now(),
          inputs: inputs,
          outputs: outputs,
          settings: settings || {}
        });
      }
      
      return outputs;
    } catch (error) {
      const endDate = new Date();
      timelineEntry.endTime = endDate.toISOString();
      timelineEntry.durationMs = endDate - startDate;
      timelineEntry.status = 'error';
      timelineEntry.errorMessage = error.message;
      this.timeline.push(timelineEntry);
      
      // Update execution context for ErrorManager
      this.errorManager.updateExecutionContext({
        timeline: this.timeline,
        nodeCount: this.flow.nodes.length,
        nodesExecuted: this.timeline.length,
        cost_summary: this._getCostSummaryFromTimeline()
      });

      // Use ErrorManager to handle the error
      this.errorManager.throwNodeError(
        node.id,
        node.type,
        `Node execution failed: ${error.message}`,
        error
      );
    }
  }

  /**
   * Process a single node
   * @param {Object} node - The node to process
   * @returns {Object} The outputs from the node
   */
  async processNode(node) {
    
    this.logDebug(`Processing node [${node.id}] of type [${node.type}]`);
    
    const nodeDefinition = this.nodes[node.type];
    if (!nodeDefinition) {
      this.logDebug(`Error: Node type "${node.type}" not found`);
      throw new Error(`Node type "${node.type}" not found.`);
    }

    // Apply default settings from node configuration
    if (!node.settings) {
      node.settings = {};
    }
    
    // Inherit default values for settings
    if (nodeDefinition.config.settings) {
      nodeDefinition.config.settings.forEach(settingDef => {
        if (settingDef.default !== undefined && (node.settings[settingDef.name] === undefined || node.settings[settingDef.name] === null || node.settings[settingDef.name] === '')) {
          this.logDebug(`Applying default value for setting [${settingDef.name}]: ${JSON.stringify(settingDef.default)}`);
          node.settings[settingDef.name] = settingDef.default;
        }
      });
    }
    
    // Collect inputs from the cache
    const inputs = {};
    this.logDebug(`Collecting inputs for node [${node.id}]`);
    
    // Get all links that connect to this node
    const nodeInputLinks = this.flow.links.filter((link) => link.to.node_id === node.id);
    
    // First, identify which input ports have connections
    const connectedInputs = new Set();
    nodeInputLinks.forEach(link => {
      connectedInputs.add(link.to.port_name);
    });
    
    // Process all connected inputs
    nodeInputLinks.forEach((link) => {
      this.logDebug(`Processing link from [${link.from.node_id}:${link.from.port_name}] to [${node.id}:${link.to.port_name}]`);
      
      const key = `${link.from.node_id}:${link.from.port_name}`;
      const inputName = link.to.port_name;
  
      const inputDef = nodeDefinition.config.inputs.find((i) => i.name === inputName);
      if (!inputDef) {
        this.logDebug(`Warning: No input definition found for port ${inputName}`);
        return;
      }

      this.logDebug(`Input definition for ${inputName}:`, inputDef);
  
      if (inputDef.allow_multiple && inputDef.refires) {
        // Refiring input: Only collect NEW values (not yet consumed)
        const lastConsumed = CacheManager.getLastConsumed(node.settings, inputName);
        
        // If never consumed before, get the latest value (for initial execution)
        if (lastConsumed === 0) {
          const latestValue = this.cache.get({ node_id: link.from.node_id, port_name: link.from.port_name });
          if (latestValue !== undefined) {
            inputs[inputName] = latestValue;
            this.logDebug(`Refiring input [${inputName}]: using initial value (never consumed):`, latestValue);
          }
        } else {
          // Get only new values since last consumption
          const newValues = this.cache.getNew({
            node_id: link.from.node_id,
            port_name: link.from.port_name,
            afterTimestamp: lastConsumed
          });
          
          this.logDebug(`Refiring input [${inputName}]: found ${newValues.length} new values since ${lastConsumed}`);
          
          if (newValues.length > 0) {
            // For refiring, use the first new value that triggered this execution
            inputs[inputName] = newValues[0];
            this.logDebug(`Setting refiring input [${inputName}] to new value:`, newValues[0]);
          }
        }
      } else if (inputDef.allow_multiple && !inputDef.refires) {
        // Non-refiring multiple input: Collect all current values
        const cachedValue = this.cache.get({ node_id: link.from.node_id, port_name: link.from.port_name });
        
        if (this.cache.has({ node_id: link.from.node_id, port_name: link.from.port_name })) {
          if(!inputs[inputName]) {
            inputs[inputName] = [];
          }
          
          // Get the value and validate its type
          const value = cachedValue;
          const itemType = inputDef.type || "any";
          
          // Validate individual item type
          if (this.typeCheck(value, itemType)) {
              inputs[inputName].push(value);
          } else {
              this.logDebug(`Type mismatch for item in multiple-input [${inputName}]: Expected ${itemType}`);
          }
        }
      } else {
        // Single value input: Always use latest value
        const cachedValue = this.cache.get({ node_id: link.from.node_id, port_name: link.from.port_name });
        
        if (this.cache.has({ node_id: link.from.node_id, port_name: link.from.port_name })) {
          this.logDebug(`Setting value for input [${inputName}]`);
          inputs[inputName] = cachedValue;
        } else if (!inputDef.required && inputDef.default !== undefined) {
          // If optional and no link value, use the default
          inputs[inputName] = inputDef.default;
          this.logDebug(`Input [${inputName}] for node [${node.id}] using default value:`, inputDef.default);
        } else {
          this.logDebug(`Warning: No value found for input [${inputName}] and no default available`);
        }
      }
    });
  
    // Now handle unconnected inputs with default values
    nodeDefinition.config.inputs.forEach((inputDef) => {
      const inputName = inputDef.name;
      
      // Skip inputs that already have values from connections
      if (connectedInputs.has(inputName) || inputs[inputName] !== undefined) {
        return;
      }
      
      // Apply default value for unconnected inputs if available
      if (inputDef.default !== undefined) {
        inputs[inputName] = inputDef.default;
        this.logDebug(`Applied default value for unconnected input [${inputName}]:`, inputDef.default);
      } else if (inputDef.required) {
        this.logDebug(`Warning: Required input [${inputName}] has no connection and no default value`);
      }
    });
  

  
    // Debug: Log inputs before processing
    this.logDebug(`Node [${node.id}] of type [${node.type}] inputs:`, JSON.stringify(inputs, null, 2));
  
    // Validate inputs against node configuration
    this.validateInputs(nodeDefinition.config, inputs);
    
    // If this node is a macro, execute its internal flow (check this FIRST before accepts_plugins)
    if (nodeDefinition.config.is_macro) {
      this.logDebug(`Node [${node.id}] is a macro. Executing internal flow.`);
      return await this.processMacroNode(node);
    }

    // If this node is an LLM that accepts plugins, use the special handler
    if (nodeDefinition.config.accepts_plugins) {
      this.logDebug(`Node [${node.id}] is an LLM with plugin support. Using processLLMNode.`);
      return await this.processLLMNode(node);
    }
    
    // Execute the process function using the shared core logic
    this.logDebug(`Executing process function for node [${node.id}]`);
    
    const outputs = await this._executeNodeCore(node, inputs, node.settings || {}, nodeDefinition);
    
    // Track this execution state to prevent future duplicates
    const executionHash = this._createExecutionHash(node.id, inputs, node.settings || {});
    this.executedNodeStates.add(executionHash);
    
    // Debug: Log outputs after processing
    this.logDebug(`Node [${node.id}] outputs:`, JSON.stringify(outputs, null, 2));
    
    // Update consumption tracking for refiring inputs
    const consumptionUpdates = {};
    const refiringInputs = nodeDefinition.config.inputs.filter(i => i.allow_multiple && i.refires);
    
    if (refiringInputs.length > 0) {
      this.logDebug(`Updating consumption tracking for ${refiringInputs.length} refiring inputs`);
      
      refiringInputs.forEach(inputDef => {
        const inputName = inputDef.name;
        
        // Find all connected links for this refiring input
        const inputLinks = this.flow.links.filter(
          link => link.to.node_id === node.id && link.to.port_name === inputName
        );
        
        // Get the latest timestamp from all connected sources
        let maxTimestamp = 0;
        inputLinks.forEach(link => {
          const timestamp = this.cache.getLatestTimestamp({
            node_id: link.from.node_id,
            port_name: link.from.port_name
          });
          if (timestamp && timestamp > maxTimestamp) {
            maxTimestamp = timestamp;
          }
        });
        
        if (maxTimestamp > 0) {
          consumptionUpdates[inputName] = maxTimestamp;
          this.logDebug(`Marking input [${inputName}] as consumed up to timestamp ${maxTimestamp}`);
        }
      });
    }
    
    // Handle updated settings
    if (outputs.__updated_settings) {
      node.settings = {
        ...node.settings,
        ...outputs.__updated_settings,
      };
      this.logDebug(`Node [${node.id}] updated settings:`, JSON.stringify(node.settings, null, 2));
      delete outputs.__updated_settings; // Remove from regular outputs
    }
    
    // Apply consumption tracking updates if any
    if (Object.keys(consumptionUpdates).length > 0) {
      node.settings = {
        ...node.settings,
        _consumption_tracking: {
          ...node.settings._consumption_tracking,
          ...consumptionUpdates
        }
      };
      this.logDebug(`Node [${node.id}] updated consumption tracking:`, node.settings._consumption_tracking);
    }
    
    // Store outputs in the cache
    for (const [key, value] of Object.entries(outputs)) {
      this.logDebug(`Storing output in cache: ${node.id}:${key}`, value);
      this.cache.set({ node_id: node.id, port_name: key, value });
    }
    
    this.logDebug(`Node [${node.id}] processing completed successfully`);
    return outputs;
  }
  
  /**
   * Propagate values through the graph
   * @param {string} nodeId - The ID of the node to start propagation from
   */
  async propagate(currentNodeId) {
    this.logDebug(`Starting propagation from node [${currentNodeId}]`);
    const visitedNodes = new Map(); // Map to track visit count per node
  
    // Check for timeout
    if (this.hasTimedOut) {
      this.errorManager.throwTimeoutError("Flow execution timed out.");
    }
    
    // Get current node definition
    const currentNode = this.flow.nodes.find((node) => node.id === currentNodeId);
    if (!currentNode) {
      this.logDebug(`Error: Node with ID "${currentNodeId}" not found`);
      throw new Error(`Node with ID "${currentNodeId}" not found.`);
    }
    
    const nodeDefinition = this.nodes[currentNode.type];
    
    // Get current visit count (for debugging only)
    const visitCount = visitedNodes.get(currentNodeId) || 0;
    
    // Increment visit count
    visitedNodes.set(currentNodeId, visitCount + 1);
    
    this.logDebug(`Processing node [${currentNodeId}] (visit #${visitCount + 1})`);
    
    this.logDebug(`Processing downstream propagation for node [${currentNodeId}]`);

    // Find all downstream nodes connected to this node
    const downstreamLinks = this.flow.links.filter((link) => {

      if(link.from.node_id === currentNodeId) {

        // did this output from nodeId actually send a value that wasn't undefined or null?
        const value = this.cache.get({ node_id: currentNodeId, port_name: link.from.port_name });
        if(value === undefined || value === null) {
          return false;
        }

        return true;
      }

      return false;
    });
    const downstreamNodes = downstreamLinks.map((link) => {
      const node = this.flow.nodes.find((node) => node.id === link.to.node_id);


      return node;
    });

    this.logDebug(`Downstream nodes: ${downstreamNodes.map(n => n?.id).join(', ')}`);

    for (const downstreamNode of downstreamNodes) {
      if (!downstreamNode) continue;

      // Skip plugin nodes that are actually connected as plugins - they should only run when called by LLM
      const isPluginNode = this.nodes[downstreamNode.type]?.config?.is_plugin;
      const isConnectedAsPlugin = this.flow.links.some(link => 
        link.from.node_id === downstreamNode.id && link.type === "plugin"
      );
      
      if (isPluginNode && isConnectedAsPlugin) {
        this.logDebug(`Skipping plugin node [${downstreamNode.id}] during propagation - will only run when called by LLM`);
        continue;
      }

      // Check if the downstream node is ready
      const nodeDefinition = this.nodes[downstreamNode.type];
      const nodeLinks = this.flow.links.filter((link) => link.to.node_id === downstreamNode.id);
      
      // Group links by input name
      const linksByInput = {};
      nodeLinks.forEach(link => {
        if (!linksByInput[link.to.port_name]) {
          linksByInput[link.to.port_name] = [];
        }
        linksByInput[link.to.port_name].push(link);
      });
      
      // Check each input
      // const isReady = Object.entries(linksByInput).every(([inputName, links]) => {
      //   const inputDef = nodeDefinition.config.inputs.find(i => i.name === inputName);
      //   if (!inputDef) return true; // Skip if no definition (shouldn't happen)
        
      //   if (inputDef.allow_multiple && inputDef.refires) {
      //     // For refiring inputs, check if ANY link has NEW values (not yet consumed)
      //     const lastConsumed = CacheManager.getLastConsumed(downstreamNode.settings, inputName);
          
      //     return links.some(link => {
      //       // If never consumed before, check if there's any value available
      //       if (lastConsumed === 0) {
      //         const hasValue = this.cache.has({ node_id: link.from.node_id, port_name: link.from.port_name });
      //         this.logDebug(`Checking refiring input [${inputName}] from ${link.from.node_id}:${link.from.port_name}, hasValue: ${hasValue} (initial execution)`);
      //         return hasValue;
      //       } else {
      //         const hasNew = this.cache.hasNew({
      //           node_id: link.from.node_id,
      //           port_name: link.from.port_name,
      //           afterTimestamp: lastConsumed
      //         });
              
      //         this.logDebug(`Checking refiring input [${inputName}] from ${link.from.node_id}:${link.from.port_name}, hasNew: ${hasNew} (after ${lastConsumed})`);
              
      //         return hasNew;
      //       }
      //     });
      //   }
        
      //   // For non-refiring inputs, ALL links must be ready
      //   return links.every(link => {
      //     if (link.type === 'plugin') return true;
          
      //     const isValueReady = this.cache.has({ node_id: link.from.node_id, port_name: link.from.port_name });
          
      //     this.logDebug(`Checking regular input [${inputName}] from ${link.from.node_id}:${link.from.port_name}, ready: ${isValueReady}`);
          
      //     if (inputDef.required) {
      //       return isValueReady;
      //     }
          
      //     return isValueReady || this.cache.get({ node_id: link.from.node_id, port_name: link.from.port_name }) === null;
      //   });
      // });
      const isReady = Object.entries(linksByInput).every(([inputName, links]) => {
        const inputDef = nodeDefinition.config.inputs.find(i => i.name === inputName);
        if (!inputDef) return true; // defensive; shouldn't normally happen
      
        // --- 1) Refiring multiple inputs (loop-start etc.) ---
        if (inputDef.allow_multiple && inputDef.refires) {
          const lastConsumed = CacheManager.getLastConsumed(downstreamNode.settings, inputName);
      
          return links.some(link => {
            if (link.type === "plugin") return false; // shouldn't be refiring anyway
      
            const { node_id, port_name } = link.from;
      
            if (lastConsumed === 0) {
              // First time: we only consider this "ready"
              // if upstream has actually produced a *non-null* value.
              const hasEntry = this.cache.has({ node_id, port_name });
              const value = this.cache.get({ node_id, port_name });
      
              const ready = hasEntry && value !== null && value !== undefined;
              this.logDebug(
                `Refiring input [${inputName}] first run from ${node_id}:${port_name}, ready: ${ready}`
              );
              return ready;
            } else {
              // Subsequent runs: only fire when there is something newer
              const hasNew = this.cache.hasNew({
                node_id,
                port_name,
                afterTimestamp: lastConsumed
              });
              this.logDebug(
                `Refiring input [${inputName}] from ${node_id}:${port_name}, hasNew: ${hasNew} (after ${lastConsumed})`
              );
              return hasNew;
            }
          });
        }
      
        // --- 2) Non-refiring inputs (your existing behavior, just made explicit) ---
      
        return links.every(link => {
          if (link.type === "plugin") return true;
      
          const { node_id, port_name } = link.from;
          const hasEntry = this.cache.has({ node_id, port_name });
          const value = this.cache.get({ node_id, port_name });
      
          this.logDebug(
            `Checking regular input [${inputName}] from ${node_id}:${port_name}, hasEntry: ${hasEntry}, value:`,
            value
          );
      
          if (inputDef.required) {
            // Required: as soon as the upstream has *any* value in history
            // (including null), we consider this satisfied.
            // This matches your previous behavior.
            return hasEntry;
          }
      
          // Optional:
          // - If no link existed in history -> false (upstream hasn't run yet).
          // - If upstream ran with either a real value or null -> true.
          //   (null meaning "ran, but intentionally no data", which is your convention.)
          return hasEntry || value === null;
        });
      });
      

      if (isReady) {
        this.logDebug(`Node [${downstreamNode.id}] is ready. Processing...`);
        
        // Use centralized method to add to queue with duplicate checking
        this.addToExecutionQueue(downstreamNode);
      } else {
        this.logDebug(`Node [${downstreamNode.id}] is not ready.`);
      }
    }
    this.logDebug(`Propagation from node [${currentNodeId}] completed`);
  }

  /**
   * Add a node to the execution queue with duplicate checking
   * This centralizes all execution queue additions and ensures nodes
   * with identical execution states (same inputs/settings) are not executed twice
   * @param {Object} node - The node to add to the execution queue
   * @returns {boolean} True if the node was added to the queue, false if it was skipped (duplicate)
   * @private
   */
  addToExecutionQueue(node) {
    try {
      const nodeDefinition = this.nodes[node.type];
      if (!nodeDefinition) {
        this.logDebug(`Warning: Cannot add node [${node.id}] to queue - node type "${node.type}" not found`);
        return false;
      }

      // Collect inputs for this node to create execution hash
      const inputs = this._collectNodeInputs(node, nodeDefinition);
      const executionHash = this._createExecutionHash(node.id, inputs, node.settings || {});
      
      // Check if this exact execution state has already been processed
      if (this.executedNodeStates.has(executionHash)) {
        this.logDebug(`Node [${node.id}] already executed with identical inputs/settings (hash: ${executionHash}), skipping queue addition`);
        return false;
      }
      
      // Check if this node is already in the queue or currently running
      if (this.queuedNodeHashes.has(executionHash)) {
        this.logDebug(`Node [${node.id}] already in queue or running with hash ${executionHash}, skipping duplicate queue addition`);
        return false;
      }
      
      // Mark as queued and add to execution queue
      this.queuedNodeHashes.add(executionHash);
      this.executionQueue.push(node);
      this.logDebug(`Added node [${node.id}] of type [${node.type}] to execution queue (hash: ${executionHash})`);
      return true;
    } catch (error) {
      this.logDebug(`Error adding node [${node.id}] to execution queue:`, error.message);
      throw error;
    }
  }

  /**
   * Collect inputs for a node (helper method for duplicate checking)
   * @param {Object} node - The node to collect inputs for
   * @param {Object} nodeDefinition - The node definition
   * @returns {Object} The collected inputs
   * @private
   */
  _collectNodeInputs(node, nodeDefinition) {
    const inputs = {};
    
    // Get all links that connect to this node
    const nodeInputLinks = this.flow.links.filter((link) => link.to.node_id === node.id);
    
    // First, identify which input ports have connections
    const connectedInputs = new Set();
    nodeInputLinks.forEach(link => {
      connectedInputs.add(link.to.port_name);
    });
    
    // Process all connected inputs
    nodeInputLinks.forEach((link) => {
      const inputName = link.to.port_name;
      const inputDef = nodeDefinition.config.inputs.find((i) => i.name === inputName);
      if (!inputDef) return;

      if (inputDef.allow_multiple && inputDef.refires) {
        // Refiring input: Only collect NEW values (not yet consumed)
        const lastConsumed = CacheManager.getLastConsumed(node.settings, inputName);
        
        if (lastConsumed === 0) {
          const latestValue = this.cache.get({ node_id: link.from.node_id, port_name: link.from.port_name });
          if (latestValue !== undefined) {
            inputs[inputName] = latestValue;
          }
        } else {
          const newValues = this.cache.getNew({
            node_id: link.from.node_id,
            port_name: link.from.port_name,
            afterTimestamp: lastConsumed
          });
          
          if (newValues.length > 0) {
            inputs[inputName] = newValues[0];
          }
        }
      } else if (inputDef.allow_multiple && !inputDef.refires) {
        // Non-refiring multiple input: Collect all current values
        const cachedValue = this.cache.get({ node_id: link.from.node_id, port_name: link.from.port_name });
        
        if (this.cache.has({ node_id: link.from.node_id, port_name: link.from.port_name })) {
          if(!inputs[inputName]) {
            inputs[inputName] = [];
          }
          
          const value = cachedValue;
          const itemType = inputDef.type || "any";
          
          if (this.typeCheck(value, itemType)) {
              inputs[inputName].push(value);
          }
        }
      } else {
        // Single value input: Always use latest value
        const cachedValue = this.cache.get({ node_id: link.from.node_id, port_name: link.from.port_name });
        
        if (this.cache.has({ node_id: link.from.node_id, port_name: link.from.port_name })) {
          inputs[inputName] = cachedValue;
        } else if (!inputDef.required && inputDef.default !== undefined) {
          inputs[inputName] = inputDef.default;
        }
      }
    });
  
    // Handle unconnected inputs with default values
    nodeDefinition.config.inputs.forEach((inputDef) => {
      const inputName = inputDef.name;
      
      if (connectedInputs.has(inputName) || inputs[inputName] !== undefined) {
        return;
      }
      
      if (inputDef.default !== undefined) {
        inputs[inputName] = inputDef.default;
      }
    });

    return inputs;
  }

  /**
   * Launch a node for parallel execution
   * @param {Object} node - The node to launch
   */
  launchNode(node) {
    this.runningNodes.add(node.id);
    this.logDebug(`Node [${node.id}] added to running set`);
    
    // Remove from queued hashes since it's now running
    // Recalculate hash to remove it from tracking
    try {
      const nodeDefinition = this.nodes[node.type];
      if (nodeDefinition) {
        const inputs = this._collectNodeInputs(node, nodeDefinition);
        const executionHash = this._createExecutionHash(node.id, inputs, node.settings || {});
        this.queuedNodeHashes.delete(executionHash);
        this.logDebug(`Removed node [${node.id}] hash ${executionHash} from queued tracking (now running)`);
      }
    } catch (error) {
      // If hash calculation fails, continue anyway - not critical
      this.logDebug(`Warning: Could not remove hash for node [${node.id}] from queued tracking:`, error.message);
    }
    
    // Execute node asynchronously
    this.processNode(node)
      .then(() => {
        // Node completed successfully
        this.runningNodes.delete(node.id);
        this.completedNodes.add(node.id);
        this.logDebug(`Node [${node.id}] completed, removed from running set`);
        
        // Propagate downstream nodes to queue
        this.propagate(node.id);
      })
      .catch((error) => {
        // Node failed
        this.runningNodes.delete(node.id);
        this.logDebug(`Node [${node.id}] failed, removed from running set:`, error.message);
        
        // Store the error for the main execution loop to handle
        this.lastError = error;
      });
  }

  /**
   * Wait for at least one node to complete
   * @returns {Promise<void>}
   */
  async waitForNodeCompletion() {
    return new Promise((resolve, reject) => {
      const checkCompletion = () => {
        if (this.runningNodes.size === 0) {
          resolve();
        } else {
          // Check again in next tick
          setImmediate(checkCompletion);
        }
      };
      
      // Start checking for completion
      setImmediate(checkCompletion);
    });
  }
  
  
  /**
   * Clean up resources including knowledge databases and temporary files
   * This should be called when the engine is no longer needed to free up memory
   * @returns {Promise<void>}
   */
  async cleanup() {
    this.logDebug('Starting cleanup process...');
    
    try {
      // Clean up main orchestration knowledge base integration
      if (this.config.integrations?.knowledgeBase) {
        this.logDebug('Cleaning up main knowledge base integration...');
        await this.config.integrations.knowledgeBase.disconnect();
        delete this.config.integrations.knowledgeBase;
      }
      
      // Also clean up legacy sqlite integration for backward compatibility
      if (this.config.integrations?.sqlite) {
        this.logDebug('Cleaning up legacy SQLite integration...');
        await this.config.integrations.sqlite.disconnect();
        delete this.config.integrations.sqlite;
      }
      
      // Clean up any imported engines that were created
      // These are stored in the cache when import nodes are processed
      const rawStore = this.cache.getRawStore();
      const importEngines = Object.values(rawStore).filter(item => 
        item && typeof item === 'object' && item.constructor?.name === 'zv1'
      );
      
      for (const importEngine of importEngines) {
        if (importEngine.cleanup) {
          this.logDebug('Cleaning up imported engine...');
          await importEngine.cleanup();
        }
      }
      
      // Clear the cache
      this.cache.clear();
      
      // Clear timeline
      this.timeline = [];
      
      // Clean up any remaining temporary knowledge base files
      await this._cleanupTempKnowledgeFiles();
      
      this.logDebug('Cleanup completed successfully');
      
    } catch (error) {
      console.warn('[WARN] Error during cleanup:', error.message);
      // Don't throw - cleanup should be best effort
    }
  }

  /**
   * Run the flow and return the final output of the flow
   * @param {Object} inputData - Data to inject into input nodes
   * @param {number} timeout - Maximum execution time in milliseconds
   * @returns {Object} The final output from output nodes
   */
  async run(inputData, timeout = 60000) {
    this.logDebug(`Starting flow execution with timeout: ${timeout}ms`);
    this.logDebug(`Input data:`, JSON.stringify(inputData, null, 2));
    
    // Clear executed states for this run
    this.executedNodeStates.clear();
    this.queuedNodeHashes.clear();

    // clear the execution queue
    this.executionQueue = [];
    this.runningNodes = new Set();
    this.completedNodes = new Set();
    
    // Update error manager with timeout context
    this.errorManager.updateExecutionContext({
      timeout: timeout,
      startTime: Date.now()
    });
    
    // Set a timeout flag to prevent infinite execution
    this.hasTimedOut = false;
    this.flowTimeout = setTimeout(() => {
      this.logDebug("Flow execution timed out");
      this.hasTimedOut = true;
    }, timeout);

    let inputsMissingValues = [];

    try {
      this.logDebug("Starting flow execution...");
  
      // Step 1: Add all entry nodes (constant nodes without inputs) to the execution queue
      for (const node of this.entryNodes) {
        this.logDebug(`Processing entry node [${node.id}] of type [${node.type}]`);
        // await this.processNode(node);
        // await this.propagate(node.id);

        this.addToExecutionQueue(node);
      }


      // Step 2: Setup and then add input nodes (if any) to the execution queue
      if (this.inputNodes.length > 0) {

        const numberOfInputDataNodes = this.inputNodes.filter(node => node.type === "input-data").length;
        const numberOfInputChatNodes = this.inputNodes.filter(node => node.type === "input-chat").length;
        const numberOfInputPromptNodes = this.inputNodes.filter(node => node.type === "input-prompt").length;

        this.logDebug(`Found ${numberOfInputDataNodes} input-data nodes, ${numberOfInputChatNodes} input-chat nodes, ${numberOfInputPromptNodes} input-prompt nodes`);

        for(const inputNode of this.inputNodes) {
          this.logDebug(`Injecting inputData into input node [${inputNode.id}]:`, inputData);
          if(!inputNode.settings) {
            inputNode.settings = {};
          }
          
          if(inputNode.type === "input-data") {
            const inputKey = inputNode.settings?.key || 'data';
            let variable_value = inputData[inputKey];

            // If the specific key is not found, try to map from the main 'data' key
            // This handles cases where .zv1 files have input-data nodes with specific keys
            // but the main flow is passing input with key 'data'
            if(variable_value === undefined && inputData.data !== undefined && inputKey !== 'data') {
              this.logDebug(`Mapping input 'data' to input-data node key '${inputKey}'`);
              variable_value = inputData.data;
            }

            if(variable_value === undefined) {
              variable_value = inputNode.settings.default_value;
            }

            if(variable_value !== undefined) {
              // await this.processNode({ ...inputNode, settings: { ...inputNode.settings, ...{value: variable_value} } });
              // await this.propagate(inputNode.id);
              this.addToExecutionQueue({ ...inputNode, settings: { ...inputNode.settings, ...{value: variable_value} } });
            } else {
              inputsMissingValues.push({
                id: inputNode.id,
                type: inputNode.type,
                key: inputNode.settings?.key || 'data'
              });
            }
          } else if(inputNode.type === "input-chat") {

            let variable_value = inputData[inputNode.settings?.key || 'chat'];

            if(variable_value !== undefined) {
              // await this.processNode({ ...inputNode, settings: { ...inputNode.settings, ...{messages: variable_value} } });
              // await this.propagate(inputNode.id);
              this.addToExecutionQueue({ ...inputNode, settings: { ...inputNode.settings, ...{messages: variable_value} } });
            } else {
              inputsMissingValues.push({
                id: inputNode.id,
                type: inputNode.type,
                key: inputNode.settings?.key || 'chat'
              });
            }

          } else if(inputNode.type === "input-prompt") {
            let variable_value = inputData[inputNode.settings?.key || 'prompt'];

            if(variable_value !== undefined) {
              // await this.processNode({ ...inputNode, settings: { ...inputNode.settings, ...{prompt: variable_value} } });
              // await this.propagate(inputNode.id);
              this.addToExecutionQueue({ ...inputNode, settings: { ...inputNode.settings, ...{prompt: variable_value} } });
            } else {
              inputsMissingValues.push({
                id: inputNode.id,
                type: inputNode.type,
                key: inputNode.settings?.key || 'prompt'
              });
            }
          } 
        }

      } else {
        this.logDebug("No input nodes found - flow will start from constant nodes");
      }

      // Step 3: Process the execution queue with parallel execution
      while(this.executionQueue.length > 0 || this.runningNodes.size > 0) {
        
        // timeout check 
        if(this.hasTimedOut) {
          this.errorManager.throwTimeoutError("Flow execution timed out.");
          break;
        }

        // Launch nodes up to concurrency limit
        while(this.executionQueue.length > 0 && this.runningNodes.size < this.maxConcurrency) {
          const node = this.executionQueue.shift();
          console.log('node to launch ', node);
          // Launch node asynchronously
          this.launchNode(node);
        }

        // Wait for at least one node to complete
        if(this.runningNodes.size > 0) {
          await this.waitForNodeCompletion();
          
          // Check for errors from parallel execution
          if(this.lastError) {
            const error = this.lastError;
            this.lastError = null; // Clear the error
            throw error; // Re-throw to be handled by the main try/catch
          }
        }
      }

      ("Execution queue is empty and no nodes running");

      // Step 4: Capture and return all output nodes' results
      const outputNodes = this.flow.nodes.filter(
        (node) => this.nodes[node.type]?.config?.is_output
      );

      this.logDebug("outputNodes", outputNodes);
      
      // If no output nodes found, return partial completion from terminal nodes
      if (outputNodes.length === 0) {
        this.logDebug("No output nodes found, returning partial completion from terminal nodes");
        
        // Find all nodes that don't have outgoing connections
        const nodesWithOutgoingLinks = new Set(
          this.flow.links.map(link => link.from.node_id)
        );
        
        const terminalNodes = this.flow.nodes.filter(
          node => !nodesWithOutgoingLinks.has(node.id)
        );

        this.logDebug(`Found ${terminalNodes.length} terminal nodes`);
        
        // Collect outputs from all terminal nodes
        const terminalOutputs = terminalNodes
          .map(node => {
            const nodeConfig = this.nodes[node.type]?.config;
            if (!nodeConfig) return null;
            const outputs = {};
            // For all outputs defined in config
            for (const output of nodeConfig.outputs) {
              const value = this.cache.get({ node_id: node.id, port_name: output.name });
              if (value === null || value === undefined) continue;
              outputs[output.name] = value;
            }

            // --- NEW: For import nodes, also include all cache keys that start with node.id + ':'
            if (node.type.startsWith('imported-')) {
              const nodeOutputs = this.cache.getNodeOutputs(node.id);
              for (const [outputName, value] of Object.entries(nodeOutputs)) {
                if (!(outputName in outputs)) {
                  outputs[outputName] = value;
                }
              }
            }
            if (Object.keys(outputs).length === 0) return null;
            return {
              node_id: node.id,
              type: node.type,
              outputs
            };
          })
          .filter(Boolean); // Remove null entries

        return {
          partial: true,
          message:  inputsMissingValues.length > 0 ? "Completed with missing input values and output nodes, results may be partial." : "Completed without output nodes.",
          terminalNodes: terminalOutputs,
          timeline: this.timeline,
          inputsMissingValues: inputsMissingValues,
          cost_summary: this._getCostSummaryFromTimeline()
        };
      }
      
      // Collect all outputs
      const finalOutputs = {};
      
      for (const node of outputNodes) {
        // Get the node's output values
        const nodeConfig = this.nodes[node.type].config;
        const nodeOutputs = nodeConfig.outputs;
        
        // check cache to see if this node returned a value for output_key

        const outputKey = node.settings?.key;
        
        let doesThisNodeHaveAKey = false;
        
        if(outputKey !== undefined && outputKey !== null && outputKey !== '') {
          doesThisNodeHaveAKey = true;
        } else {
          doesThisNodeHaveAKey = false;
        }

        this.logDebug("nodeOutputs", nodeOutputs);

        const numberOfOutputDataNodes = nodeOutputs.filter(output => output.name === "value").length;
        const numberOfOutputChatNodes = nodeOutputs.filter(output => output.name === "chat").length;
        const numberOfOutputPromptNodes = nodeOutputs.filter(output => output.name === "prompt").length;

        this.logDebug(`Found ${numberOfOutputDataNodes} output-data nodes, ${numberOfOutputChatNodes} output-chat nodes, ${numberOfOutputPromptNodes} output-prompt nodes`);

        let dataIndex = 0;
        let chatIndex = 0;
        
        for (const output of nodeOutputs) {
          
          if (this.cache.has({ node_id: node.id, port_name: output.name })) {
            const value = this.cache.get({ node_id: node.id, port_name: output.name });
            
            // Skip null/undefined values
            if (value === null || value === undefined) continue;

            // if this node.type is a data output, add the value to .data if no key is provided - otherwise add the value to the outputs with the key
            if(node.type === "output-data") {
              if(doesThisNodeHaveAKey ) {
                // if the key is provided, add the value to the outputs with the key
                finalOutputs[outputKey] = value;
              } else if(numberOfOutputDataNodes > 1) {
                finalOutputs['data_' + dataIndex] = value;
                dataIndex++;
              } else {
                finalOutputs['data'] = value;
              }
            } else if(node.type === "output-chat") {
              // if this node.type is a chat output, add the value to the conversation object
              
              if(doesThisNodeHaveAKey) {
                finalOutputs[outputKey] = value;
              } else if(numberOfOutputChatNodes > 1) {
                finalOutputs['chat_' + chatIndex] = value;
                chatIndex++;
              } else {
                finalOutputs['chat'] = value;
              }
            }
          }
        }
      }
      
      this.logDebug("Flow execution complete. Final outputs:", finalOutputs);
      clearTimeout(this.flowTimeout);

      return {
        outputs: finalOutputs,
        timeline: this.timeline,
        cost_summary: this._getCostSummaryFromTimeline(),
        inputsMissingValues: inputsMissingValues,
        message:  inputsMissingValues.length > 0 ? "Completed with missing input values, results may be partial." : "Completed."
      };
    } catch (error) {
      // Clear the timeout on error
      clearTimeout(this.flowTimeout);
      
      // If this is a timeout error, add it to the timeline
      if (error.errorType === 'timeout') {
        // Create a timeline entry for the timeout
        const timeoutEntry = {
          nodeId: 'system',
          nodeType: 'timeout',
          inputs: {},
          settings: {},
          startTime: new Date(this.errorManager.executionContext.startTime).toISOString(),
          endTime: new Date().toISOString(),
          durationMs: Date.now() - this.errorManager.executionContext.startTime,
          status: 'error',
          errorMessage: error.message
        };
        this.timeline.push(timeoutEntry);
        
        // Update error manager context with final timeline
        this.errorManager.updateExecutionContext({
          timeline: this.timeline,
          nodesExecuted: this.timeline.length
        });
      }
      
      // Re-throw to propagate to the caller
      throw error;
    } finally {
      clearTimeout(this.flowTimeout);
    }
  }

  /**
   * Process a macro node by executing its internal flow
   * @param {Object} node - The macro node to process
   * @returns {Object} The outputs from the macro
   */
  async processMacroNode(node) {
    this.logDebug(`Processing macro node [${node.id}] of type [${node.type}]`);
    
    const nodeDefinition = this.nodes[node.type];
    const macroConfig = nodeDefinition.config;
    
    // Create timeline entry for macro execution
    const startDate = new Date();
    const timelineEntry = {
      node_id: node.id,
      type: node.type,
      startTime: startDate.toISOString(),
      status: 'running'
    };
    this.timeline.push(timelineEntry);
    
    
    try {
      // Create internal flow from macro_flow
      const internalFlow = {
        nodes: [...macroConfig.macro_flow.nodes],
        links: [...macroConfig.macro_flow.links]
      };
      
      // Prepare tools object for internal engine if this macro accepts plugins
      let tools = {};
      
      if (macroConfig.accepts_plugins && macroConfig.plugins && macroConfig.plugins.length > 0) {
        this.logDebug(`Macro [${node.id}] accepts plugins, creating tool runners for parent context execution`);
        
        // Find all plugin nodes connected to this macro in the parent flow
        const externalPluginNodeIds = this.flow.links
          .filter(link => link.type === "plugin" && link.to.node_id === node.id)
          .map(link => link.from.node_id);
        
        this.logDebug(`Found ${externalPluginNodeIds.length} external plugins connected to macro [${node.id}]`);
        
        // Create tool definitions for each external plugin
        for (const externalPluginNodeId of externalPluginNodeIds) {
          const externalPluginNode = this.flow.nodes.find(n => n.id === externalPluginNodeId);
          if (externalPluginNode) {
            // Generate the tool schema from the parent context
            const schema = this.generateToolSchema(externalPluginNode);
            
            // Create a tool runner that executes in PARENT context
            const toolRunner = async (args) => {
              this.logDebug(`Tool runner called for [${schema.name}] from internal macro engine`);
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
    
    // Create internal zv1 instance
    const internalEngine = new zv1(internalFlow, {
      ...this.config,
      // Pass through integrations and other config
      integrations: this.config.integrations,
      keys: this.config.keys,
      debug: this.config.debug,
      // Pass tools from parent context
      tools: Object.keys(tools).length > 0 ? tools : undefined,
      // Conditionally disable event firing for internal engine
      // If includeInternalEvents is true, pass through the event handlers
      onNodeStart: this.config.includeInternalEvents ? this.config.onNodeStart : null,
      onNodeComplete: this.config.includeInternalEvents ? this.config.onNodeComplete : null,
      onNodeError: this.config.includeInternalEvents ? this.config.onNodeError : null
    });
    
    // Share executed states with internal engine to prevent duplicate execution
    internalEngine.executedNodeStates = this.executedNodeStates;
    
    // Initialize the internal engine
    await internalEngine.initialize();
    
    // Map macro inputs to internal flow inputs
    const internalInputs = {};
    macroConfig.inputs.forEach(inputDef => {
      const inputValue = this.getNodeInputValue(node, inputDef.name);
      if (inputValue !== undefined) {
        internalInputs[inputDef.name] = inputValue;
      }
    });


    // Fire onNodeStart event (matching the convention used in _executeNodeCore)
    if (this.config.onNodeStart) {
      await this.config.onNodeStart({
        nodeId: node.id,
        nodeType: node.type,
        timestamp: Date.now(),
        inputs: internalInputs,
        settings: node.settings || {}
      });
    }
    
    this.logDebug(`Macro [${node.id}] internal inputs:`, JSON.stringify(internalInputs, null, 2));
    
    // Create execution hash to check for duplicate processing
    const executionHash = this._createExecutionHash(node.id, internalInputs, node.settings || {});
    
    // Skip if this exact execution state has already been processed
    if (this.executedNodeStates.has(executionHash)) {

      this.logDebug(`Macro [${node.id}] already executed with identical inputs/settings (hash: ${executionHash}), skipping`);
      
      // Complete timeline entry for skipped execution
      const endDate = new Date();
      timelineEntry.endTime = endDate.toISOString();
      timelineEntry.durationMs = endDate - startDate;
      timelineEntry.status = 'skipped';
      timelineEntry.outputs = {};
      
      // Fire onNodeComplete event for skipped execution
      if (this.config.onNodeComplete) {
        await this.config.onNodeComplete({
          nodeId: node.id,
          nodeType: node.type,
          timestamp: Date.now(),
          outputs: {},
          durationMs: endDate - startDate
        });
      }
      
      return {}; // Return empty outputs to avoid downstream processing
    }
    
    // Execute the internal flow
    const internalResult = await internalEngine.run(internalInputs);
    
    // Map internal outputs back to macro outputs
    const macroOutputs = {};
    macroConfig.outputs.forEach(outputDef => {
      // Look for the output in the internal engine's cache
      // The output-data node stores its value in the cache with key "output_node_id:value"
      const outputNodeId = `output_${outputDef.name}`;
      const outputValue = internalEngine.cache.get({ node_id: outputNodeId, port_name: 'value' });
      
      if (outputValue !== undefined) {
        macroOutputs[outputDef.name] = outputValue;
      }
    });
    
    this.logDebug(`Macro [${node.id}] outputs:`, JSON.stringify(macroOutputs, null, 2));
    
    // Store macro outputs in the main engine's cache for downstream propagation
    for (const [outputName, outputValue] of Object.entries(macroOutputs)) {
      this.cache.set({ node_id: node.id, port_name: outputName, value: outputValue });
      this.logDebug(`Stored macro output in cache: ${node.id}:${outputName}`, outputValue);
    }
    
      // Complete timeline entry
      const endDate = new Date();
      timelineEntry.endTime = endDate.toISOString();
      timelineEntry.durationMs = endDate - startDate;
      timelineEntry.status = 'completed';
      timelineEntry.outputs = JSON.parse(JSON.stringify(macroOutputs));
      
      // Fire onNodeComplete event (matching the convention used in _executeNodeCore)
      if (this.config.onNodeComplete) {
        await this.config.onNodeComplete({
          nodeId: node.id,
          nodeType: node.type,
          timestamp: Date.now(),
          outputs: JSON.parse(JSON.stringify(macroOutputs)),
          durationMs: endDate - startDate
        });
      }
      
      // Track this execution state
      this.executedNodeStates.add(executionHash);
      
      return macroOutputs;
    } catch (error) {
      // Update timeline entry with error
      const endDate = new Date();
      timelineEntry.endTime = endDate.toISOString();
      timelineEntry.durationMs = endDate - startDate;
      timelineEntry.status = 'error';
      timelineEntry.errorMessage = error.message;
      
      // Fire onNodeError event (matching the convention used in _executeNodeCore)
      if (this.config.onNodeError) {
        await this.config.onNodeError({
          nodeId: node.id,
          nodeType: node.type,
          timestamp: Date.now(),
          error: error.message,
          durationMs: endDate - startDate
        });
      }
      
      throw error;
    }
  }

  /**
   * Get input value for a specific node and input name
   * @param {Object} node - The node to get input for
   * @param {string} inputName - The name of the input
   * @returns {any} The input value or undefined
   */
  getNodeInputValue(node, inputName) {
    // Find the link that connects to this input
    const link = this.flow.links.find(link => 
      link.to.node_id === node.id && link.to.port_name === inputName
    );
    
    if (!link) {
      this.logDebug(`No link found for input ${inputName} on node ${node.id}`);
      return undefined;
    }
    
    const value = this.cache.get({ node_id: link.from.node_id, port_name: link.from.port_name });
    
    this.logDebug(`Getting input value for ${node.id}.${inputName} from ${link.from.node_id}:${link.from.port_name}:`, value);
    
    return value;
  }
  
  /**
   * Clean up the flow by removing invalid links
   * @private
   */
  sanitizeFlow() {
    const nodeIds = new Set(this.flow.nodes.map(node => node.id));
    
    // Filter out links that reference non-existent nodes
    const originalLength = this.flow.links.length;
    this.flow.links = this.flow.links.filter(link => 
      nodeIds.has(link.from.node_id) && nodeIds.has(link.to.node_id)
    );
    
    const removedCount = originalLength - this.flow.links.length;
    if (removedCount > 0) {
      this.logDebug(`Removed ${removedCount} invalid link(s) referencing non-existent nodes`);
    }
  }

  /**
   * Scan for plugin links and map LLM nodes to their plugin/tool nodes
   */
  initializePluginMappings() {
    this.llmPlugins = {};
    for (const node of this.flow.nodes) {
      if (this.nodes[node.type]?.config?.accepts_plugins) {
        this.llmPlugins[node.id] = this.flow.links
          .filter(link => link.type === "plugin" && link.to.node_id === node.id)
          .map(link => link.from.node_id);
      }
    }
  }

  /**
   * Main entry for processing LLM nodes with plugins/tools
   */
  async processLLMNode(node) {
    this.logDebug(`Processing LLM node [${node.id}] of type [${node.type}]`);
    
    const nodeDefinition = this.nodes[node.type];
    if (!nodeDefinition) {
      this.logDebug(`Error: Node type "${node.type}" not found`);
      throw new Error(`Node type "${node.type}" not found.`);
    }

    // Apply default settings from node configuration (same as processNode)
    if (!node.settings) {
      node.settings = {};
    }
    
    // Inherit default values for settings
    if (nodeDefinition.config.settings) {
      nodeDefinition.config.settings.forEach(settingDef => {
        if (settingDef.default !== undefined && (node.settings[settingDef.name] === undefined || node.settings[settingDef.name] === null || node.settings[settingDef.name] === '')) {
          this.logDebug(`Applying default value for setting [${settingDef.name}]: ${JSON.stringify(settingDef.default)}`);
          node.settings[settingDef.name] = settingDef.default;
        }
      });
    }
    
    // Collect inputs using the same logic as processNode (same as processNode)
    const inputs = {};
    this.logDebug(`Collecting inputs for LLM node [${node.id}]`);
    
    // Get all links that connect to this node
    const nodeInputLinks = this.flow.links.filter((link) => link.to.node_id === node.id);
    
    // First, identify which input ports have connections
    const connectedInputs = new Set();
    nodeInputLinks.forEach(link => {
      connectedInputs.add(link.to.port_name);
    });
    
    // Process all connected inputs
    nodeInputLinks.forEach((link) => {
      this.logDebug(`Processing link from [${link.from.node_id}:${link.from.port_name}] to [${node.id}:${link.to.port_name}]`);
      
      const key = `${link.from.node_id}:${link.from.port_name}`;
      const inputName = link.to.port_name;
  
      const inputDef = nodeDefinition.config.inputs.find((i) => i.name === inputName);
      if (!inputDef) {
        this.logDebug(`Warning: No input definition found for port ${inputName}`);
        return;
      }

      this.logDebug(`Input definition for ${inputName}:`, inputDef);
  
      if (inputDef.allow_multiple && inputDef.refires) {
        // Refiring input: Only collect NEW values (not yet consumed)
        const lastConsumed = CacheManager.getLastConsumed(node.settings, inputName);
        
        // If never consumed before, get the latest value (for initial execution)
        if (lastConsumed === 0) {
          const latestValue = this.cache.get({ node_id: link.from.node_id, port_name: link.from.port_name });
          if (latestValue !== undefined) {
            inputs[inputName] = latestValue;
            this.logDebug(`LLM refiring input [${inputName}]: using initial value (never consumed):`, latestValue);
          }
        } else {
          // Get only new values since last consumption
          const newValues = this.cache.getNew({
            node_id: link.from.node_id,
            port_name: link.from.port_name,
            afterTimestamp: lastConsumed
          });
          
          this.logDebug(`LLM refiring input [${inputName}]: found ${newValues.length} new values since ${lastConsumed}`);
          
          if (newValues.length > 0) {
            // For refiring, use the first new value that triggered this execution
            inputs[inputName] = newValues[0];
            this.logDebug(`Setting LLM refiring input [${inputName}] to new value:`, newValues[0]);
          }
        }
      } else if (inputDef.allow_multiple && !inputDef.refires) {
        // Non-refiring multiple input: Collect all current values
        const cachedValue = this.cache.get({ node_id: link.from.node_id, port_name: link.from.port_name });
        
        if (this.cache.has({ node_id: link.from.node_id, port_name: link.from.port_name })) {
          if(!inputs[inputName]) {
            inputs[inputName] = [];
          }
          
          // Get the value and validate its type
          const value = cachedValue;
          const itemType = inputDef.type || "any";
          
          // Validate individual item type
          if (this.typeCheck(value, itemType)) {
              inputs[inputName].push(value);
          } else {
              this.logDebug(`Type mismatch for item in multiple-input [${inputName}]: Expected ${itemType}`);
          }
        }
      } else {
        // Single value input: Always use latest value
        const cachedValue = this.cache.get({ node_id: link.from.node_id, port_name: link.from.port_name });
        
        if (this.cache.has({ node_id: link.from.node_id, port_name: link.from.port_name })) {
          this.logDebug(`Setting value for LLM input [${inputName}]`);
          inputs[inputName] = cachedValue;
        } else if (!inputDef.required && inputDef.default !== undefined) {
          // If optional and no link value, use the default
          inputs[inputName] = inputDef.default;
          this.logDebug(`Input [${inputName}] for LLM node [${node.id}] using default value:`, inputDef.default);
        } else {
          this.logDebug(`Warning: No value found for LLM input [${inputName}] and no default available`);
        }
      }
    });
  
    // Now handle unconnected inputs with default values
    nodeDefinition.config.inputs.forEach((inputDef) => {
      const inputName = inputDef.name;
      
      // Skip inputs that already have values from connections
      if (connectedInputs.has(inputName) || inputs[inputName] !== undefined) {
        return;
      }
      
      // Apply default value for unconnected inputs if available
      if (inputDef.default !== undefined) {
        inputs[inputName] = inputDef.default;
        this.logDebug(`Applied default value for unconnected input [${inputName}]:`, inputDef.default);
      } else if (inputDef.required) {
        this.logDebug(`Warning: Required input [${inputName}] has no connection and no default value`);
      }
    });

    // Debug: Log inputs before processing
    this.logDebug(`LLM Node [${node.id}] of type [${node.type}] inputs:`, JSON.stringify(inputs, null, 2));
  
    // Validate inputs against node configuration (same as processNode)
    this.validateInputs(nodeDefinition.config, inputs);

    // Create execution hash to check for duplicate processing
    const executionHash = this._createExecutionHash(node.id, inputs, node.settings || {});
    
    // Skip if this exact execution state has already been processed
    if (this.executedNodeStates.has(executionHash)) {
      this.logDebug(`LLM Node [${node.id}] already executed with identical inputs/settings (hash: ${executionHash}), skipping`);
      return {}; // Return empty outputs to avoid downstream processing
    }

    // 1. Gather plugin/tool schemas and runners
    const toolSchemas = [];
    const toolRunners = {}; // toolName -> handler

    // First, check if there are tools provided from config (parent context or developer-provided)
    if (this.config.tools && typeof this.config.tools === 'object' && !Array.isArray(this.config.tools)) {
      this.logDebug(`Found ${Object.keys(this.config.tools).length} tools from config`);
      for (const [toolName, toolDef] of Object.entries(this.config.tools)) {
        // If schema is provided, add it to the list
        if (toolDef.schema) {
          toolSchemas.push(toolDef.schema);
          this.logDebug(`Loaded tool schema from config: ${toolName}`);
        }
        // Always register the process function if provided
        if (toolDef.process) {
          toolRunners[toolName] = toolDef.process;
          this.logDebug(`Loaded tool runner from config: ${toolName}`);
        }
      }
    }

    // Then, discover local plugins (these can override or supplement parent tools)
    const pluginNodeIds = this.llmPlugins[node.id] || [];
    for (const pluginNodeId of pluginNodeIds) {
      const pluginNode = this.flow.nodes.find(n => n.id === pluginNodeId);
      if (!pluginNode) continue;

      if (this.isLocalNodePlugin(pluginNode)) {
        const schema = this.generateToolSchema(pluginNode);
        toolSchemas.push(schema);
        
        const nodeDefinition = this.nodes[pluginNode.type];
        
        // Special handling for macro nodes
        if (nodeDefinition?.config?.is_macro) {
          this.logDebug(`Node [${pluginNode.id}] is a macro plugin. Using processMacroNode.`);
          toolRunners[schema.name] = async (args) => {
            // Merge LLM args with static inputs
            const staticInputs = this.collectStaticInputs(pluginNode);
            const mergedInputs = { ...staticInputs, ...args };
            this.logDebug(`Merged inputs for macro plugin [${pluginNode.id}]:`, mergedInputs);
            
            // For macros, we need to temporarily add the args to the cache
            const tempCacheKeys = [];
            
            // Store args in cache as if they came from upstream nodes
            for (const [inputName, value] of Object.entries(mergedInputs)) {
              const tempNodeId = `__plugin_arg_${pluginNode.id}`;
              this.cache.set({ node_id: tempNodeId, port_name: inputName, value });
              tempCacheKeys.push({ node_id: tempNodeId, port_name: inputName });
              
              // Add a temporary link so getNodeInputValue can find it
              const tempLink = {
                from: { node_id: tempNodeId, port_name: inputName },
                to: { node_id: pluginNode.id, port_name: inputName }
              };
              this.flow.links.push(tempLink);
            }
            
            try {
              // Execute the macro
              const outputs = await this.processMacroNode(pluginNode);
              
              // Store outputs in cache for downstream propagation
              this.logDebug(`Storing macro plugin outputs in cache:`, outputs);
              for (const [key, value] of Object.entries(outputs)) {
                this.cache.set({ node_id: pluginNode.id, port_name: key, value });
              }
              
              // Propagate outputs downstream
              await this.propagate(pluginNode.id);
              
              return outputs;
            } finally {
              // Clean up temporary cache entries and links
              tempCacheKeys.forEach(({ node_id, port_name }) => 
                this.cache.delete({ node_id, port_name })
              );
              this.flow.links = this.flow.links.filter(link => 
                !link.from.node_id.startsWith('__plugin_arg_')
              );
            }
          };
        }
        // Check if this is an imported node with chat inputs
        else if (nodeDefinition?.config?.is_import && 
          nodeDefinition.config.inputs?.some(input => input.is_chat_input)) {
          toolRunners[schema.name] = async (args) => {
            // Merge LLM args with static inputs
            const staticInputs = this.collectStaticInputs(pluginNode);
            const mergedInputs = { ...staticInputs, ...args };
            this.logDebug(`Merged inputs for chat plugin [${pluginNode.id}]:`, mergedInputs);
            
            // Execute the plugin node
            const outputs = await this.processImportedChatNode(pluginNode, mergedInputs);
            
            // Store outputs in cache for downstream propagation
            this.logDebug(`Storing plugin outputs in cache for downstream propagation:`, outputs);
            for (const [key, value] of Object.entries(outputs)) {
              this.cache.set({ node_id: pluginNode.id, port_name: key, value });
            }
            
            // Propagate outputs downstream (if any downstream connections exist)
            await this.propagate(pluginNode.id);
            
            return outputs;
          };
        } else {
          toolRunners[schema.name] = async (args) => {
            // Merge LLM args with static inputs
            const staticInputs = this.collectStaticInputs(pluginNode);
            const mergedInputs = { ...staticInputs, ...args };
            this.logDebug(`Merged inputs for plugin [${pluginNode.id}]:`, mergedInputs);
            
            // Execute the plugin node
            const outputs = await this.processNodeWithArgs(pluginNode, mergedInputs);
            
            // Store outputs in cache for downstream propagation
            this.logDebug(`Storing plugin outputs in cache for downstream propagation:`, outputs);
            for (const [key, value] of Object.entries(outputs)) {
              this.cache.set({ node_id: pluginNode.id, port_name: key, value });
            }
            
            // Propagate outputs downstream (if any downstream connections exist)
            await this.propagate(pluginNode.id);
            
            return outputs;
          };
        }
      } else if (isRemoteMCPTool(pluginNode)) {
        // Fetch all tools from the MCP endpoint
        const url = pluginNode.settings?.url;
        if (!url) continue; 
        const id = uuidv4();
        try {
          
          const response = await axios.post(url, {
            id,
            method: "tools/list",
            params: {}
          });
          const tools = response.data?.result?.tools || [];
          for (const tool of tools) {
            // Add each tool as a separate schema
            toolSchemas.push({
              name: tool.name,
              description: tool.description,
              parameters: tool.inputSchema
            });
            // Map tool name to a runner that calls this MCP node/tool
            toolRunners[tool.name] = async (args) => {
              return await callMCPTool(pluginNode, { ...args, name: tool.name });
            };
          }
        } catch (err) {
          this.logDebug(`Failed to fetch MCP tools from ${url}: ${err.message}`);
        }
      } else if (isManualToolNode(pluginNode)) {
        const schema = this.generateToolSchema(pluginNode);
        toolSchemas.push(schema);
        // Manual tools: no runner, just pass through
      }
    }

    // --- Also gather manual tool nodes connected to the LLM's 'tools' input port ---
    const toolInputLinks = this.flow.links.filter(
      link => link.to.node_id === node.id && link.to.port_name === "tools"
    );
    for (const link of toolInputLinks) {
      // the schema should be grabbable from the node's output cache on its "tool" output
      const toolSchema = this.cache.get({ node_id: link.from.node_id, port_name: 'tool' });
      if(toolSchema) {
        // Only add schema if developer hasn't already provided one via config
        // If config.tools has this tool name but no schema, developer wants to use flow schema with their process
        const configTool = this.config.tools?.[toolSchema.name];
        if (!configTool || !configTool.schema) {
          toolSchemas.push(toolSchema);
          this.logDebug(`Loaded manual tool schema from flow: ${toolSchema.name}`);
        } else {
          this.logDebug(`Skipping flow schema for ${toolSchema.name} - using config schema instead`);
        }
      }
    }
    

    // 2. Inject toolSchemas into LLM call
    let llmResult;
    let tool_results = [];
    let toolCallMessage = null;
    let toolCallCount = 0;

    do {
      llmResult = await this.callLLMWithTools(node, inputs, toolSchemas, toolCallMessage, tool_results);
      tool_results = [];
      toolCallMessage = null;

      if (llmResult.tool_calls && llmResult.tool_calls.length > 0) {
        
        for (const tool_call of llmResult.tool_calls) {

          if(tool_call.type === 'function'){
            if (toolRunners[tool_call.function.name]) {

              // try to parse the arguments as a JSON object
              let toolArguments = tool_call.function.arguments;
              try {
                toolArguments = JSON.parse(tool_call.function.arguments);

                const toolResult = await toolRunners[tool_call.function.name](toolArguments);
                tool_results.push({
                  original_tool_call: tool_call,
                  tool_call_id: tool_call.id,
                  name: tool_call.function.name,
                  result: toolResult
                });
              } catch (e) {
                console.error('Failed to parse tool arguments as JSON', e);
              }
            } else {
              console.error('No runner found for tool', tool_call.name);
            }
          }
        }
        // Prepare the tool call message for the next LLM call
        toolCallMessage = {
          role: "assistant",
          content: null,
          tool_calls: llmResult.tool_calls
        };
        toolCallCount++;
      } else {
        break; // No more tool calls, exit loop
      }
    } while (tool_results.length > 0 && toolCallCount < this.maxPluginCalls);

    // 4. Continue with normal LLM output processing
    // Store outputs in the cache and propagate downstream
    for (const output of nodeDefinition.config.outputs || []) {
      if (llmResult[output.name] !== undefined) {
        this.cache.set({ node_id: node.id, port_name: output.name, value: llmResult[output.name] });
      }
    }
    
    // Debug: Log outputs after processing
    this.logDebug(`LLM Node [${node.id}] outputs:`, JSON.stringify(llmResult, null, 2));
    
    // Handle updated settings
    if (llmResult.__updated_settings) {
      node.settings = {
        ...node.settings,
        ...llmResult.__updated_settings,
      };
      this.logDebug(`LLM Node [${node.id}] updated settings:`, JSON.stringify(node.settings, null, 2));
      delete llmResult.__updated_settings; // Remove from regular outputs
    }
    
    // Track this execution state
    this.executedNodeStates.add(executionHash);
    
    this.logDebug(`LLM Node [${node.id}] processing completed successfully`);
    return llmResult;
  }

  /**
   * Execute a plugin node in the parent context with all its dependencies
   * This allows plugins to be called from internal engines (macros/imports) 
   * while maintaining their connections in the parent flow
   * @param {Object} pluginNode - The plugin node to execute
   * @param {Object} args - Arguments from the tool call
   * @returns {Object} The outputs from the plugin
   */
  async executePluginInParentContext(pluginNode, args) {
    this.logDebug(`Executing plugin [${pluginNode.id}] in parent context with args:`, args);
    
    const nodeDefinition = this.nodes[pluginNode.type];
    if (!nodeDefinition) {
      throw new Error(`Node type "${pluginNode.type}" not found.`);
    }
    
    // Check if this is a macro or import node (needs special handling)
    if (nodeDefinition.config.is_macro) {
      this.logDebug(`Plugin [${pluginNode.id}] is a macro, using processMacroNode`);
      
      // For macros called as plugins, we need to temporarily add the args to the cache
      // so the macro can access them via getNodeInputValue
      const tempCacheKeys = [];
      
      // Store args in cache as if they came from upstream nodes
      for (const [inputName, value] of Object.entries(args)) {
        const tempNodeId = `__plugin_arg_${pluginNode.id}`;
        this.cache.set({ node_id: tempNodeId, port_name: inputName, value });
        tempCacheKeys.push({ node_id: tempNodeId, port_name: inputName });
        
        // Also add a temporary link so getNodeInputValue can find it
        const tempLink = {
          from: { node_id: tempNodeId, port_name: inputName },
          to: { node_id: pluginNode.id, port_name: inputName }
        };
        this.flow.links.push(tempLink);
      }
      
      // Execute the macro
      const outputs = await this.processMacroNode(pluginNode);
      
      // Clean up temporary cache entries and links
      tempCacheKeys.forEach(({ node_id, port_name }) => 
        this.cache.delete({ node_id, port_name })
      );
      this.flow.links = this.flow.links.filter(link => 
        !link.from.node_id.startsWith('__plugin_arg_')
      );
      
      return outputs;
    }
    
    // For regular nodes and imports
    // Collect static inputs (from parent flow connections)
    const staticInputs = this.collectStaticInputs(pluginNode);
    
    // Merge static inputs with LLM-provided args
    const mergedInputs = { ...staticInputs, ...args };
    
    this.logDebug(`Merged inputs for plugin [${pluginNode.id}]:`, mergedInputs);
    
    // Execute the plugin node with merged inputs
    const outputs = await this.processNodeWithArgs(pluginNode, mergedInputs);
    
    // Store outputs in parent cache for downstream propagation
    this.logDebug(`Storing plugin outputs in parent cache:`, outputs);
    for (const [key, value] of Object.entries(outputs)) {
      this.cache.set({ node_id: pluginNode.id, port_name: key, value });
    }
    
    // Propagate outputs downstream in parent context
    await this.propagate(pluginNode.id);
    
    return outputs;
  }

  isLocalNodePlugin(node) {
    const thisNodeConfig = this.nodes[node.type]?.config || {};
    return thisNodeConfig.is_plugin || thisNodeConfig.is_macro;
  }

  isNodeReady(node) {
    const nodeDefinition = this.nodes[node.type];
    if (!nodeDefinition) throw new Error(`Node type "${node.type}" not found.`);
    for (const inputDef of nodeDefinition.config.inputs || []) {
      if (!inputDef.required) continue;
      const inputName = inputDef.name;
      const incomingLink = this.flow.links.find(
        link => link.to.node_id === node.id && link.to.port_name === inputName
      );
      if (incomingLink) {
        if (!this.cache.has({ node_id: incomingLink.from.node_id, port_name: incomingLink.from.port_name })) {
          return false;
        }
      }
    }
    return true;
  }

  /**
   * Collect statically connected inputs for a plugin node
   * @param {Object} node - The plugin node to collect inputs for
   * @returns {Object} The statically connected inputs
   */
  collectStaticInputs(node) {
    const config = this.nodes[node.type]?.config || {};
    const staticInputs = {};
    
    // Find all statically connected inputs (non-plugin links)
    const staticLinks = this.flow.links.filter(link => 
      link.to.node_id === node.id && link.type !== "plugin"
    );
    
    this.logDebug(`Collecting static inputs for plugin node [${node.id}]:`, staticLinks.map(l => `${l.from.node_id}:${l.from.port_name} -> ${l.to.port_name}`));
    
    staticLinks.forEach(link => {
      const inputName = link.to.port_name;
      const inputDef = config.inputs?.find(input => input.name === inputName);
      
      if (!inputDef) {
        this.logDebug(`Warning: No input definition found for static input ${inputName}`);
        return;
      }
      
      const value = this.cache.get({ node_id: link.from.node_id, port_name: link.from.port_name });
      
      if (value !== undefined) {
        if (inputDef.allow_multiple) {
          // Initialize or reset the array for this run
          if (!staticInputs[inputName]) {
            staticInputs[inputName] = [];
          }
          
          // Get the value and validate its type
          const itemType = inputDef.type || "any";
          
          // Validate individual item type
          if (this.typeCheck(value, itemType)) {
            staticInputs[inputName].push(value);
          } else {
            this.logDebug(`Type mismatch for static input [${inputName}]: Expected ${itemType}`);
          }
        } else {
          staticInputs[inputName] = value;
        }
        
        this.logDebug(`Collected static input [${inputName}]:`, value);
      } else {
        this.logDebug(`Warning: No value found for static input [${inputName}]`);
      }
    });
    
    // Handle unconnected inputs with default values
    config.inputs?.forEach(inputDef => {
      const inputName = inputDef.name;
      
      // Skip if already has a value from static connections
      if (staticInputs[inputName] !== undefined) {
        return;
      }
      
      // Apply default value for unconnected inputs if available
      if (inputDef.default !== undefined) {
        staticInputs[inputName] = inputDef.default;
        this.logDebug(`Applied default value for static input [${inputName}]:`, inputDef.default);
      }
    });
    
    return staticInputs;
  }

  generateToolSchema(node) {
    // Get the node config and settings
    const config = this.nodes[node.type]?.config || {};
    const settings = node.settings || {};

    // Use the node's custom display name name/description if present, otherwise fall back to config
    let name = node.display_name || config.display_name || node.type;
    name = createSafeToolName(name);

    const description = node.description || config.description || "";

    // Find which inputs are statically connected (not available to LLM)
    const staticallyConnectedInputs = new Set();
    this.flow.links.forEach(link => {
      if (link.to.node_id === node.id && link.type !== "plugin") {
        staticallyConnectedInputs.add(link.to.port_name);
      }
    });

    // Build JSON Schema properties for each input that is NOT statically connected
    const properties = {};
    const required = [];
    (config.inputs || []).forEach(input => {
      // Skip inputs that are statically connected - LLM shouldn't see these
      if (staticallyConnectedInputs.has(input.name)) {
        return;
      }

      if(config.is_import){
        if(input.is_data_input){
          properties[input.name] = {
            type: input.type || "object",
            description: input.description || "",
          };
        } else if(input.is_chat_input){
          properties[input.name] = {
            type: "string",
            description: "A conversational chat message to send to this agent."
          };
        } else if(input.is_prompt_input){
          properties[input.name] = {
            type: "string",
            description: input.description || "",
          };
        }
        if (input.required) {
          required.push(input.name);
        }
      } else {
        properties[input.name] = {
          type: mapTypeToJSONSchema(input.type),
          description: input.description || "",
        };
        if (input.default !== undefined) {
          properties[input.name].default = input.default;
        }
        if (input.required) {
          required.push(input.name);
        }
      }
    });


    // Return the tool schema object
    return {
      name,
      description,
      parameters: {
        type: "object",
        properties,
        required,
      }
    };
  }


  /**
   * Process imported nodes with chat inputs, maintaining conversation state per chat key
   * @param {Object} node - The imported node to process
   * @param {Object} args - Arguments from the LLM tool call
   * @returns {Object} The outputs from the node
   */
  async processImportedChatNode(node, args) {
    this.logDebug('processImportedChatNode', node.id, args);

    const nodeDefinition = this.nodes[node.type];
    if (!nodeDefinition || !nodeDefinition.config.is_import) {
      throw new Error(`Node ${node.id} is not an imported node`);
    }

    // Initialize conversation state if it doesn't exist
    if (!this._conversationState) {
      this._conversationState = {};
    }

    // Find the imported flow definition to get the actual input-chat nodes
    const importDef = nodeDefinition.config.importDefinition;
    const inputChatNodes = importDef.nodes.filter(n => n.type === 'input-chat');
    
    // Transform string arguments to message arrays for each chat input
    const transformedArgs = { ...args };
    
    for (const chatInput of nodeDefinition.config.inputs.filter(input => input.is_chat_input)) {
      const inputValue = args[chatInput.name];
      if (typeof inputValue === 'string') {
        
        // Find the corresponding input-chat node to get its key
        const inputChatNode = inputChatNodes.find(n => n.id === chatInput.name);
        const chatKey = inputChatNode?.settings?.key || 'chat';
        
        // Create conversation key: nodeId + chatKey for this specific chat stream
        const conversationKey = `${node.id}_${chatKey}`;
        
        if (!this._conversationState[conversationKey]) {
          this._conversationState[conversationKey] = [];
        }

        // Add the new user message to this chat stream's history
        this._conversationState[conversationKey].push({
          role: 'user',
          content: inputValue
        });
        
        // Pass the full conversation history for this chat stream
        transformedArgs[chatInput.name] = [...this._conversationState[conversationKey]];
        
        this.logDebug(`Updated conversation for ${conversationKey}:`, this._conversationState[conversationKey]);
      }
    }

    // Process the imported node with the full conversation context
    const outputs = await this.processNodeWithArgs(node, transformedArgs);

    // Handle responses from output-chat nodes and append to appropriate conversation streams
    const outputChatNodes = importDef.nodes.filter(n => n.type === 'output-chat');
    
    for (const outputChatNode of outputChatNodes) {
      const chatKey = outputChatNode.settings?.key || 'chat';
      const conversationKey = `${node.id}_${chatKey}`;
      
      // Look for this output-chat node's result by its ID (not chat key)
      const chatOutput = outputs[outputChatNode.id];
      
      this.logDebug(`Looking for output from node ${outputChatNode.id} with chat key ${chatKey}:`, chatOutput);
      
      if (chatOutput && Array.isArray(chatOutput)) {
        if (!this._conversationState[conversationKey]) {
          this._conversationState[conversationKey] = [];
        }
        
        // The chat output contains new response messages to append
        // (not the full conversation history)
        if (chatOutput.length > 0) {
          this._conversationState[conversationKey].push(...chatOutput);
          this.logDebug(`Appended ${chatOutput.length} new messages to conversation ${conversationKey}:`, chatOutput);
        }
      } else {
        this.logDebug(`No chat output found for node ${outputChatNode.id}, available outputs:`, Object.keys(outputs));
      }
    }

    return outputs;
  }

  /**
   * Reset conversation state for specific chat streams or all conversations
   * @param {string} nodeId - Optional node ID to reset conversations for
   * @param {string} chatKey - Optional chat key to reset specific chat stream
   */
  resetConversationState(nodeId = null, chatKey = null) {
    if (!this._conversationState) return;
    
    if (nodeId && chatKey) {
      const conversationKey = `${nodeId}_${chatKey}`;
      delete this._conversationState[conversationKey];
      this.logDebug(`Reset conversation state for node ${nodeId}, chat key ${chatKey}`);
    } else if (nodeId) {
      // Reset all chat streams for this node
      const keysToDelete = Object.keys(this._conversationState).filter(key => 
        key.startsWith(`${nodeId}_`)
      );
      keysToDelete.forEach(key => delete this._conversationState[key]);
      this.logDebug(`Reset all conversation states for node ${nodeId}`);
    } else {
      this._conversationState = {};
      this.logDebug('Reset all conversation states');
    }
  }

  async processNodeWithArgs(node, args) {
    this.logDebug('processNodeWithArgs', node, args);

    const nodeDefinition = this.nodes[node.type];
    if (!nodeDefinition) throw new Error(`Node type "${node.type}" not found.`);

    // For import nodes, their process function expects (inputs, settings, config)
    // For regular nodes, same signature
    // We'll use node.settings or an empty object
    const settings = node.settings || {};
    
    // Validate the merged inputs against the node configuration
    this.validateInputs(nodeDefinition.config, args);
    
    // Execute using the shared core logic
    const outputs = await this._executeNodeCore(node, args, settings, nodeDefinition);

    this.logDebug('processNodeWithArgs outputs', outputs);
    return outputs;
  }


  async callLLMWithTools(node, inputs, toolSchemas, toolCallMessage, toolResults) {
    const nodeDefinition = this.nodes[node.type];
    if (!nodeDefinition) throw new Error(`Node type "${node.type}" not found.`);

    // Use the inputs passed from processLLMNode instead of re-collecting them
    const llmInputs = { ...inputs };
    
    // Inject the tools array
    llmInputs.tools = toolSchemas;

    // If this is a tool call response, append it to the messages array (OpenAI style)
    if (toolCallMessage && toolResults && Array.isArray(llmInputs.messages)) {

      // 
      llmInputs.messages = [
        ...llmInputs.messages,
        toolCallMessage
      ];

      for(const toolResult of toolResults) {
        // You may need to adapt this for other LLMs
          llmInputs.messages = [
            ...llmInputs.messages,
            {
              role: "tool",
              tool_call_id: toolResult.tool_call_id,
              name: toolResult.name,
              content: typeof toolResult.result === "string"
                ? toolResult.result
                : JSON.stringify(toolResult.result)
            }
          ];
      }
    }

    // Execute using the shared core logic
    const outputs = await this._executeNodeCore(node, llmInputs, node.settings || {}, nodeDefinition);

    return outputs;
  }

  _getCostSummaryFromTimeline() {
    let total = 0;
    let itemized = [];
    for (const entry of this.timeline) {
      const outputs = entry.outputs || {};
      if (typeof outputs.cost_total === 'number') {
        total += outputs.cost_total;

        let item = {
          node_id: entry.nodeId,
          node_type: entry.nodeType,
          total: outputs.cost_total,
          itemized: outputs.cost_itemized
        }
        itemized.push(item);
      }
    }
    
    return { 
      total, 
      itemized
    };
  }

  /**
   * Track a knowledge base file for cleanup
   * @param {string} filePath - Path to the knowledge base file
   */
  trackKnowledgeFile(filePath) {
    if (filePath && filePath.includes('knowledge_')) {
      this.knowledgeFilesToCleanup.add(filePath);
      this.logDebug(`Tracking knowledge file for cleanup: ${filePath}`);
    }
  }

  /**
   * Track all knowledge base files that need cleanup
   * @private
   */
  _trackKnowledgeFiles() {
    // Track main flow's knowledge base file
    if (this.flow.knowledgeDbPath) {
      this.trackKnowledgeFile(this.flow.knowledgeDbPath);
    }

    // Track import knowledge base files
    if (this.flow.imports && Array.isArray(this.flow.imports)) {
      for (const importDef of this.flow.imports) {
        if (importDef.knowledgeDbPath) {
          this.trackKnowledgeFile(importDef.knowledgeDbPath);
        }
      }
    }
  }

  /**
   * Clean up temporary knowledge base files for this specific engine instance
   * @private
   */
  async _cleanupTempKnowledgeFiles() {
    
    try {
      const fs = await import('fs');
      const path = await import('path');
      
      const tempDir = path.join(process.cwd(), '.temp');
      if (!fs.existsSync(tempDir)) {
        return; // No temp directory exists
      }

      // Clean up tracked knowledge files first
      for (const filePath of this.knowledgeFilesToCleanup) {
        try {
          if (fs.existsSync(filePath)) {
            fs.unlinkSync(filePath);
            this.logDebug(`Cleaned up tracked knowledge file: ${filePath}`);
          }
          
          // Also clean up any lock files
          const lockPath = `${filePath}.lock`;
          if (fs.existsSync(lockPath)) {
            fs.unlinkSync(lockPath);
            this.logDebug(`Cleaned up lock file: ${lockPath}`);
          }
        } catch (error) {
          console.warn(`[WARN] Failed to cleanup tracked knowledge file ${filePath}:`, error.message);
        }
      }

      // Get the flow ID to identify our specific temporary files
      const flowId = this.flow.id || this.flow.metadata?.id;
      if (!flowId) {
        this.logDebug('No flow ID found, skipping additional knowledge file cleanup');
        return;
      }

      // Look for any remaining knowledge files that match our flow ID pattern
      const files = fs.readdirSync(tempDir);
      const knowledgeFiles = files.filter(file => file === `knowledge_${flowId}.db`);


      for (const file of knowledgeFiles) {
        const filePath = path.join(tempDir, file);
        const lockPath = `${filePath}.lock`;
        
        try {
          fs.unlinkSync(filePath);
          this.logDebug(`Cleaned up additional temporary knowledge file: ${filePath}`);
        } catch (error) {
          console.warn(`[WARN] Failed to cleanup additional temporary knowledge file ${filePath}:`, error.message);
        }
        
        // Also clean up any lock files
        try {
          if (fs.existsSync(lockPath)) {
            fs.unlinkSync(lockPath);
            this.logDebug(`Cleaned up lock file: ${lockPath}`);
          }
        } catch (error) {
          // Ignore lock file cleanup errors
        }
      }

      // Also clean up any knowledge files that are older than 1 hour (safety cleanup)
      const oneHourAgo = Date.now() - (60 * 60 * 1000);
      const allKnowledgeFiles = files.filter(file => file.startsWith('knowledge_') && file.endsWith('.db'));
      
      for (const file of allKnowledgeFiles) {
        const filePath = path.join(tempDir, file);
        try {
          const stats = fs.statSync(filePath);
          if (stats.mtime.getTime() < oneHourAgo) {
            fs.unlinkSync(filePath);
            this.logDebug(`Cleaned up old temporary knowledge file: ${filePath}`);
          }
        } catch (error) {
          // Ignore errors for old file cleanup
        }
      }

      // If temp directory is now empty, remove it
      try {
        const remainingFiles = fs.readdirSync(tempDir);
        if (remainingFiles.length === 0) {
          fs.rmdirSync(tempDir);
          this.logDebug('Removed empty temporary directory');
        }
      } catch (error) {
        // Ignore errors for directory cleanup
      }

    } catch (error) {
      console.warn('[WARN] Error during temporary knowledge file cleanup:', error.message);
      // Don't throw - cleanup should be best effort
    }
  }
}
