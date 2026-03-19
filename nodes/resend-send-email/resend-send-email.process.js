export default async ({ inputs, settings, config }) => {
  const resend = config.integrations?.resend;
  if (!resend) {
    throw new Error("Resend integration not configured. Add your Resend API key to config.keys.resend");
  }

  if (!inputs.to) throw new Error("to is required");
  if (!inputs.from) throw new Error("from is required");
  if (!inputs.subject) throw new Error("subject is required");
  if (!inputs.text && !inputs.html) throw new Error("Either text or html body is required");

  const result = await resend.sendEmail({
    to: inputs.to,
    from: inputs.from,
    subject: inputs.subject,
    text: inputs.text || undefined,
    html: inputs.html || undefined,
    replyTo: inputs.reply_to || undefined,
    cc: inputs.cc || undefined,
    bcc: inputs.bcc || undefined,
  });

  return {
    id: result?.id || null,
  };
};
