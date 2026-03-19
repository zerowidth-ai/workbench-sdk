export default async ({ inputs, settings, config }) => {
  const integrations = config.integrations || {};
  const sendgrid = integrations.sendgrid;

  if (!sendgrid) {
    throw new Error(
      "SendGrid integration not configured. Add your SendGrid API key to config.keys.sendgrid"
    );
  }

  const to = inputs.to;
  const from = inputs.from;
  const subject = inputs.subject;

  if (!to) {
    throw new Error("to is required");
  }
  if (!from) {
    throw new Error("from is required");
  }
  if (!subject) {
    throw new Error("subject is required");
  }
  if (!inputs.text && !inputs.html) {
    throw new Error("Either text or html body is required");
  }

  await sendgrid.sendEmail({
    to,
    from,
    fromName: inputs.from_name || undefined,
    subject,
    text: inputs.text || undefined,
    html: inputs.html || undefined,
    replyTo: inputs.reply_to || undefined,
    cc: inputs.cc || undefined,
    bcc: inputs.bcc || undefined,
  });

  return {
    message: "Email accepted for delivery",
  };
};
