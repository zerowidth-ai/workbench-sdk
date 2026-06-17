import Workbench from '../../src/index.js';

async function runInputOutputTypesExample() {
  try {
    console.log('🔄 Running Input/Output Types Example');
    console.log('=====================================');
    
    // Create engine instance
    const engine = await Workbench.create('./flow.json');
    
    // Demonstrate different input types
    const inputData = {
      // input-data type: simple string value
      user_name: "Alice",
      
      // input-chat type: array of chat messages
      conversation: [
        { role: "user", content: "Hello there!" },
        { role: "assistant", content: "Hi! How can I help you today?" },
        { role: "user", content: "I'm learning about Workbench flows." }
      ],
      
      // input-prompt type: string prompt/instruction
      system_prompt: "You are a helpful AI assistant focused on teaching."
    };
    
    console.log('📥 Input Data:');
    console.log('  user_name:', inputData.user_name);
    console.log('  conversation:', JSON.stringify(inputData.conversation, null, 2));
    console.log('  system_prompt:', inputData.system_prompt);
    console.log('');
    
    // Run the flow
    const result = await engine.run(inputData);
    
    console.log('📤 Output Results:');
    console.log('  user_name_output (from output-data):', result.outputs.user_name_output);
    console.log('  system_prompt_output (from output-data):', result.outputs.system_prompt_output);
    console.log('  conversation_output (from output-chat):');
    console.log('   ', JSON.stringify(result.outputs.conversation_output, null, 2));
    console.log('');
    
    console.log('📊 Execution Summary:');
    console.log('  Total nodes executed:', result.timeline.length);
    console.log('  Execution time:', result.timeline.reduce((total, entry) => total + entry.durationMs, 0), 'ms');
    console.log('  Status:', result.message);
    
    // Show which input types were processed
    const inputNodes = result.timeline.filter(entry => entry.nodeType.startsWith('input-'));
    console.log('');
    console.log('🎯 Input Types Processed:');
    inputNodes.forEach(node => {
      console.log(`  ${node.nodeType}: ${node.nodeId}`);
    });
    
  } catch (error) {
    console.log(error);
    console.error('❌ Error:', error.message);
  }
}

// Run the example
runInputOutputTypesExample();