export default async ({ inputs, settings, config }) => {
  const slack = config.integrations?.slack;
  if (!slack) {
    throw new Error("Slack integration not configured. Add your Slack Bot token to config.keys.slack");
  }

  if (!inputs.channel) throw new Error("channel is required");
  if (!inputs.text) throw new Error("text is required");

  const result = await slack.postMessage(inputs.channel, inputs.text, {
    thread_ts: inputs.thread_ts || undefined,
  });

  return {
    message: result.message,
    ts: result.ts,
    channel: result.channel,
  };
};
