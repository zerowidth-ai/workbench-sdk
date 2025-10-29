import { isOAuthKey } from './oauth.js';

/**
 * Validate keys for all nodes that specify `needs_key_from`
 */
export function validateKeys() {
  this.logDebug("Validating required API keys for nodes...");
  
  for (const [nodeType, nodeDefinition] of Object.entries(this.nodes)) {
    const needsKeyFrom = nodeDefinition.config.needs_key_from;
    if (!needsKeyFrom) continue;

    const requiredKeys = Array.isArray(needsKeyFrom) ? needsKeyFrom : [needsKeyFrom];
    const missingKeys = requiredKeys.filter((key) => {
      // Key is missing if it doesn't exist in this.keys
      if (!(key in this.keys)) {
        return true;
      }
      
      const keyValue = this.keys[key];
      
      // Check if it's an OAuth key and validate its structure
      if (isOAuthKey && isOAuthKey(keyValue)) {
        // OAuth keys are valid if they have accessToken and onRefresh
        // (already checked by isOAuthKey)
        return false;
      }
      
      // For non-OAuth keys, they're valid if they exist (string or object)
      return false;
    });

    if (missingKeys.length > 0) {
      this.logDebug(`Missing required keys for node type '${nodeType}': ${missingKeys.join(", ")}`);
      throw new Error(
        `Node type '${nodeType}' requires the following missing keys: ${missingKeys.join(", ")}`
      );
    }

    this.logDebug(`All required keys for node type '${nodeType}' are present.`);
  }
  
  this.logDebug("Key validation completed successfully");
}

/**
 * Ensure this flow can run
 */
export function validateFlow(flow) {
  // First validate all links reference existing nodes
  const nodeIds = new Set(flow.nodes.map(node => node.id));
  const invalidLinks = flow.links.filter(
    link => !nodeIds.has(link.from.node_id) || !nodeIds.has(link.to.node_id)
  );

  if (invalidLinks.length > 0) {
    this.logDebug("Found invalid links referencing non-existent nodes:", invalidLinks);
    throw new Error(
      `Flow contains ${invalidLinks.length} invalid link(s) referencing non-existent nodes: ` +
      invalidLinks.map(link => `${link.from.node_id} -> ${link.to.node_id}`).join(", ")
    );
  }

  // Find input nodes
  const inputNodes = flow.nodes.filter((node) => this.nodes[node.type]?.config?.is_input);

  // Find nodes that can act as entry points:
  const entryNodes = flow.nodes.filter((node) => {
    const isConstant = this.nodes[node.type]?.config?.is_constant;
    if (!isConstant) return false;
    // Check if this node has any input connections
    const hasInputs = flow.links.some((link) => link.to.node_id === node.id);
    if (hasInputs) return false;
    // Exclude if node is_plugin and is linked as a plugin
    const isPlugin = this.nodes[node.type]?.config?.is_plugin;
    const isLinkedAsPlugin = flow.links.some(
      (link) => link.type === "plugin" && link.from.node_id === node.id
    );
    if (isPlugin && isLinkedAsPlugin) return false;
    return true;
  });
  
  this.logDebug(`Found ${inputNodes.length} input nodes${inputNodes.length ? ': ' + inputNodes.map(n => n.id).join(', ') : ''}`);
  this.logDebug(`Found ${entryNodes.length} entry nodes${entryNodes.length ? ': ' + entryNodes.map(n => n.id).join(', ') : ''}`);
  
  // Ensure there's at least one entry point
  if (inputNodes.length === 0 && entryNodes.length === 0) {
    throw new Error("Flow must have at least one input node or constant node without inputs to start execution");
  }

  this.inputNodes = inputNodes;
  this.entryNodes = entryNodes;
}


/**
 * Validate inputs against the node's configuration
 * @param {Object} nodeConfig - The node's configuration
 * @param {Object} inputs - The inputs to validate
 */
export function validateInputs(nodeConfig, inputs) {
  
  this.logDebug("Validating inputs against node config:", JSON.stringify(inputs, null, 2));
  
  // validate each input
  nodeConfig.inputs.forEach((inputDef) => {
    const { name, type, required } = inputDef;
    const value = inputs[name];

    // check if required and missing
    if (required && (value === undefined || value === null)) {
      this.logDebug(`Validation error: Missing required input: ${name}`);
      throw new Error(nodeConfig.display_name + ` is missing required input: ${name}`);
    }

    // check if type matches
    if (value !== undefined && !this.typeCheck(value, type)) {
      this.logDebug(`Validation error: Type mismatch for input '${name}': Expected ${type}, got ${JSON.stringify(value)}`);
      throw new Error(nodeConfig.display_name + ` has a type mismatch for input '${name}': Expected ${type}, got ${JSON.stringify(value)}`);
    }
    
    this.logDebug(`Input '${name}' validation passed`);
  });
}