import { createHash } from "crypto";

export default async ({ inputs, settings, config }) => {
  const content = inputs.content;
  const algorithm = inputs.algorithm ?? "sha256";

  let stringContent;
  if (typeof content === "string") {
    stringContent = content;
  } else if (content === null || content === undefined) {
    stringContent = "";
  } else {
    stringContent = JSON.stringify(content);
  }

  const hash = createHash(algorithm).update(stringContent, "utf-8").digest("hex");

  return { hash };
};
