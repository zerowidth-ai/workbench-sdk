export default async ({inputs, settings, config, nodeConfig}) => {

  const messages = settings.messages || [];
  let messageText = null;

  if (messages.length > 0) {
    const mostRecentMessage = messages[messages.length - 1];

    // content will either be a string or an array of objects where one object might have a type: "text" and a text property
    messageText = mostRecentMessage.content;

    if (Array.isArray(messageText)) {
      const textItem = messageText.find(item => item.type === "text");
      messageText = textItem ? textItem.text : null;
    }

    if (!messageText || messageText === '') {
      messageText = null;
    }
  }

  // For each message, remove the id, participant_id and timestamp fields without mutating originals
  const cleanedMessages = messages.map(({id, participant_id, timestamp, ...rest}) => rest);

  return {
    messages: cleanedMessages,
    message: messageText
  };
}; 