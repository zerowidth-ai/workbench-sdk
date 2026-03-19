import OpenAI from 'openai';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class OpenRouterIntegration {
    constructor(apiKey, options = {}) {
        
        this.client = new OpenAI({
            baseURL: options.baseURL || 'https://openrouter.ai/api/v1',
            apiKey: apiKey,
            defaultHeaders: {
                'Content-Type': 'application/json',
                'HTTP-Referer': options.referer || 'https://zv1.ai',
                'X-Title': options.title || 'zv1 by ZeroWidth'
            }
        });
    }

    async chatCompletion(params, nodeConfig = null, engineConfig = null) {
        const {
            model,
            messages,
            prompt,
            ...otherParams
        } = params;

        // Base payload with required fields
        const payload = {
            model,
            provider: {
                data_collection: "deny",
                require_parameters: true,
            }
        };

        // Add messages or prompt (required)
        if (messages) {
            payload.messages = messages;

            // Remove internal fields without mutating the original messages
            payload.messages = payload.messages.map(message => {
              const { id, participant_id, timestamp, ...clean } = message;
              if (clean.tool_calls !== undefined && clean.tool_calls.length === 0) {
                delete clean.tool_calls;
              }
              return clean;
            });

        } else if (prompt) {
            payload.prompt = prompt;
        } else {
            throw new Error('Either messages or prompt must be provided');
        }

        // if we have tools, we need to wrap each in {type: 'function', function: {name: 'tool_name', arguments: 'tool_arguments'}}
        if (otherParams.tools) {
            otherParams.tools = otherParams.tools.map(tool => ({
                type: 'function',
                function: {
                    name: tool.name,
                    description: tool.description,
                    parameters: tool.parameters
                }
            }));
        }

        // Dynamically add parameters that have values
        for (const [key, value] of Object.entries(otherParams)) {
            if (value !== null && value !== undefined) {
                // Handle special parameter mappings
                if (key === 'reasoning') {
                    // Handle reasoning parameter - can be boolean or object
                    if (typeof value === 'boolean') {
                        payload.reasoning = { enabled: value };
                    } else if (typeof value === 'object') {
                        payload.reasoning = value;
                    }
                } else if (key === 'include_reasoning') {
                    // Legacy support: treat as reasoning toggle
                    if (typeof value === 'boolean' && !payload.reasoning) {
                        payload.reasoning = { enabled: value };
                    }
                } else {
                    // Pass through all other parameters
                    payload[key] = value;
                }
            }
        }


        delete payload.system_prompt;
        if(payload.tools && payload.tools.length === 0){
          delete payload.tools;
        }

        const apiCallStartTime = Date.now();
        const isImageRequest = Array.isArray(payload.modalities) && payload.modalities.includes('image');

        try {
            // Image models: use non-streaming to preserve images field (OpenAI SDK strips it from stream deltas)
            if (isImageRequest) {
                return await this._nonStreamingCompletion(payload, nodeConfig, engineConfig, apiCallStartTime);
            }

            payload.stream = true;

            const stream = await this.client.chat.completions.create(JSON.parse(JSON.stringify(payload)));

            let content = "";
            let role = "";
            let finish_reason = "";
            let native_finish_reason = "";
            let refusal = "";
            let reasoning = "";
            let annotations = [];
            let images = [];
            let tool_calls = [];

            let usage = {
              prompt_tokens: 0,
              completion_tokens: 0,
              total_tokens: 0
            }

            let count = 0;
            for await (const chunk of stream) {
              switch(chunk.object){
                case 'chat.completion.chunk':
                  let event = {
                    count: count,
                    nodeType: nodeConfig.type,
                    nodeId: nodeConfig.id,
                    timestamp: new Date().getTime(),
                    data: {}
                  }

                  if(chunk.choices[0]){
                    if(chunk.choices[0].delta){
                      event.data = {
                        ...event.data,
                        content: chunk.choices[0].delta.content,
                        reasoning: chunk.choices[0].delta.reasoning,
                        role: chunk.choices[0].delta.role,
                        tool_calls: chunk.choices[0].delta.tool_calls,
                        images: chunk.choices[0].delta.images,
                        finish_reason: chunk.choices[0].delta.finish_reason,
                        native_finish_reason: chunk.choices[0].delta.native_finish_reason,
                      }
                    } else if(chunk.choices[0].text){
                      event.data = {
                        ...event.data,
                        content: chunk.choices[0].text,
                      }
                    }
                  }

                  if(event.data.content != null){
                    content += event.data.content;
                  }

                  if(event.data.reasoning != null){
                    reasoning += event.data.reasoning;
                  }

                  if(!event.data.role){
                    event.data.role = "assistant";
                  }
                  
                  role = event.data.role;
                  
                  if(event.data.tool_calls && event.data.tool_calls.length > 0){
                    let tool_call = event.data.tool_calls[0];
                    if(tool_call.id){
                      tool_calls.push({
                        id: tool_call.id,
                        index: tool_call.index,
                        type: tool_call.type,
                        function: tool_call.function
                      });
                    } else {
                      // grab the most recent tool call and append the tool_call.function.arguments to the end of the tool_calls[i].function.arguments
                      let mostRecentToolCall = tool_calls[tool_calls.length - 1];
                      if(mostRecentToolCall){
                        mostRecentToolCall.function.arguments += tool_call.function.arguments;
                      }
                    }
                  }

                  // Accumulate images from delta (OpenRouter returns images in delta.images)
                  if(chunk.choices[0]?.delta?.images && Array.isArray(chunk.choices[0].delta.images)){
                    images.push(...chunk.choices[0].delta.images);
                  }

                  if(event.data.finish_reason){
                    finish_reason = event.data.finish_reason;
                  }

                  if(chunk.usage){
                    usage.prompt_tokens += chunk.usage.prompt_tokens || 0;
                    usage.completion_tokens += chunk.usage.completion_tokens || 0;
                    usage.total_tokens += chunk.usage.total_tokens || 0;
                  }

                  if(engineConfig?.onNodeUpdate){
                    engineConfig.onNodeUpdate(event);
                  }

                  count++;

                  break;
                default:
              }
            }

            // Calculate costs if nodeConfig is provided
            let costData = null;
            
            if (nodeConfig && nodeConfig.pricing) {
                costData = this.calculateCosts(usage, nodeConfig.pricing);
            }

            const result = {
                content,
                role,
                finish_reason,
                tool_calls,
                model,
                usage,
                refusal,
                reasoning,
                annotations,
                images: images.length > 0 ? images : undefined,
                ...(costData && {
                    cost_total: costData.totalCost,
                    cost_itemized: costData.itemizedCosts
                }),
            };


            // Emit API call event after stream is consumed
            await emitAPICallEvent(engineConfig || this._engineConfig, {
                timestamp: apiCallStartTime,
                integration: 'openrouter',
                nodeId: nodeConfig?.id || null,
                nodeType: nodeConfig?.type || null,
                request: {
                    method: 'POST',
                    url: `${this.client.baseURL}/chat/completions`,
                    headers: {
                        'Content-Type': 'application/json',
                        'HTTP-Referer': this.client._options?.defaultHeaders?.['HTTP-Referer'] || 'https://zv1.ai',
                        'X-Title': this.client._options?.defaultHeaders?.['X-Title'] || 'zv1 by ZeroWidth',
                        'Authorization': `Bearer ${this.client._options?.apiKey || ''}`
                    },
                    body: payload
                },
                response: { status: 200, statusText: 'OK', body: result },
                duration: Date.now() - apiCallStartTime,
                error: null
            });

            return result;
        } catch (error) {
            // Parse error details from OpenAI SDK error shape
            const status = error.status || error.response?.status || 0;
            const statusText = error.response?.statusText || (status ? `HTTP ${status}` : 'Error');
            const errorBody = error.error || error.response?.data || null;
            const errorCode = error.code || errorBody?.error?.code || null;
            const errorType = error.type || errorBody?.error?.type || null;

            let errorMessage = `OpenRouter API Error`;
            if (status) errorMessage += ` (${status})`;

            // Extract the most specific error message available
            const specificMessage = errorBody?.error?.message
                || errorBody?.message
                || (typeof errorBody === 'string' ? errorBody : null)
                || error.message;
            if (specificMessage) errorMessage += `: ${specificMessage}`;

            // Emit API call event with full error detail
            await emitAPICallEvent(engineConfig || this._engineConfig, {
                timestamp: apiCallStartTime,
                integration: 'openrouter',
                nodeId: nodeConfig?.id || null,
                nodeType: nodeConfig?.type || null,
                request: {
                    method: 'POST',
                    url: `${this.client.baseURL}/chat/completions`,
                    headers: {
                        'Content-Type': 'application/json',
                        'HTTP-Referer': this.client._options?.defaultHeaders?.['HTTP-Referer'] || 'https://zv1.ai',
                        'X-Title': this.client._options?.defaultHeaders?.['X-Title'] || 'zv1 by ZeroWidth',
                        'Authorization': `Bearer ${this.client._options?.apiKey || ''}`
                    },
                    body: payload
                },
                response: {
                    status,
                    statusText,
                    body: errorBody
                },
                duration: Date.now() - apiCallStartTime,
                error: {
                    message: errorMessage,
                    code: errorCode,
                    type: errorType,
                    status,
                    raw: error.message
                }
            });

            console.error('OpenRouter Integration Error:', errorMessage);

            throw new Error(errorMessage);
        }
    }

    /**
     * Non-streaming completion for image models.
     * Bypasses the OpenAI SDK entirely because it strips OpenRouter-specific
     * fields like `images` from both streaming deltas and non-streaming messages.
     * Uses raw fetch to preserve the full response.
     */
    async _nonStreamingCompletion(payload, nodeConfig, engineConfig, apiCallStartTime) {
        const url = `${this.client.baseURL}/chat/completions`;
        const headers = {
            'Content-Type': 'application/json',
            'HTTP-Referer': this.client._options?.defaultHeaders?.['HTTP-Referer'] || 'https://zv1.ai',
            'X-Title': this.client._options?.defaultHeaders?.['X-Title'] || 'zv1 by ZeroWidth',
            'Authorization': `Bearer ${this.client._options?.apiKey || ''}`
        };

        const res = await fetch(url, {
            method: 'POST',
            headers,
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const errorBody = await res.json().catch(() => null);
            const errorMessage = errorBody?.error?.message || `HTTP ${res.status}`;
            throw new Error(`OpenRouter API Error (${res.status}): ${errorMessage}`);
        }

        const data = await res.json();
        const choice = data.choices?.[0];
        const message = choice?.message || {};
        const usage = data.usage || { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };

        let costData = null;
        if (nodeConfig?.pricing) {
            costData = this.calculateCosts(usage, nodeConfig.pricing);
        }

        // Image models return data on choice directly (text, images, reasoning)
        // rather than nested under choice.message
        const result = {
            content: message.content || choice?.text || '',
            role: message.role || 'assistant',
            finish_reason: choice?.finish_reason || '',
            tool_calls: message.tool_calls || [],
            model: payload.model,
            usage,
            refusal: message.refusal || '',
            reasoning: message.reasoning || choice?.reasoning || '',
            annotations: message.annotations || [],
            images: message.images || choice?.images || undefined,
            ...(costData && {
                cost_total: costData.totalCost,
                cost_itemized: costData.itemizedCosts
            }),
        };

        // Emit API call event
        await emitAPICallEvent(engineConfig || this._engineConfig, {
            timestamp: apiCallStartTime,
            integration: 'openrouter',
            nodeId: nodeConfig?.id || null,
            nodeType: nodeConfig?.type || null,
            request: {
                method: 'POST',
                url,
                headers,
                body: payload
            },
            response: { status: res.status, statusText: res.statusText, body: result },
            duration: Date.now() - apiCallStartTime,
            error: null
        });

        return result;
    }

    /**
     * Calculate costs based on usage and pricing
     */
    calculateCosts(usage, pricing) {
      
        const items = pricing.items || [];
        const inputCostObj = items.find(p => p.key === 'input_cost_per_million');
        const outputCostObj = items.find(p => p.key === 'output_cost_per_million');
        
        const promptTokens = usage.prompt_tokens || 0;
        const completionTokens = usage.completion_tokens || 0;
        
        const inputTokenCost = (inputCostObj?.cost || 0) / 1_000_000;
        const outputTokenCost = (outputCostObj?.cost || 0) / 1_000_000;
        
        let inputCost = promptTokens * inputTokenCost;
        let outputCost = completionTokens * outputTokenCost;
        let totalCost = inputCost + outputCost;

        // Round to 8 decimal places
        totalCost = Number(totalCost.toFixed(8));
        inputCost = Number(inputCost.toFixed(8));
        outputCost = Number(outputCost.toFixed(8));

        return {
            totalCost,
            itemizedCosts: [
                { label: "Input Tokens", cost: inputCost, tokens: promptTokens },
                { label: "Output Tokens", cost: outputCost, tokens: completionTokens }
            ]
        };
    }
}