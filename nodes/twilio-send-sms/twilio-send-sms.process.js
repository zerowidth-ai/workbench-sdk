export default async ({ inputs, settings, config }) => {
  const twilio = config.integrations?.twilio;
  if (!twilio) {
    throw new Error("Twilio integration not configured. Add your Twilio config to config.keys.twilio ({account_sid, auth_token})");
  }

  if (!inputs.to) throw new Error("to is required");
  if (!inputs.from) throw new Error("from is required");
  if (!inputs.body) throw new Error("body is required");

  const result = await twilio.sendSMS(inputs.to, inputs.from, inputs.body);

  return {
    sid: result.sid,
    status: result.status,
  };
};
