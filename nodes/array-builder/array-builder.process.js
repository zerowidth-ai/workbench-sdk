export default async ({inputs, settings, config, nodeConfig}) => {

  const items = inputs.items;

  if (items === undefined || items === null) {
    return { array: [] };
  }

  const array = Array.isArray(items) ? items : [items];

  return { array };
};
