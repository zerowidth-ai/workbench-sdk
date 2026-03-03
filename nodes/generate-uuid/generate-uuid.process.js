import { randomUUID } from "crypto";

export default async ({ inputs, settings, config }) => {
  const count = Math.max(1, Math.floor(inputs.count || 1));

  const uuids = [];
  for (let i = 0; i < count; i++) {
    uuids.push(randomUUID());
  }

  return {
    uuid: uuids[0],
    uuids,
  };
};
